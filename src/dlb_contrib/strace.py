# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Detect read and written filesystem objects of a running process with strace."""

# strace: <https://strace.io/>
# Tested with: strace 4.26
# Executable: 'strace'
#
# Usage example:
#
#   from typing import Iterable, List, Tuple, Union
#   import dlb.ex
#   import dlb_contrib.strace
#
#   class ShowContent(dlb_contrib.strace.RunStraced):
#       EXECUTABLE = 'bash'
#
#       def get_command_line(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
#           return ['-c', '-', 'cat  -- *', 's']
#
#   with dlb.ex.Context():
#       ... = ShowContent().start().read_files

__all__ = ['SYSCALL_NAME_REGEX', 'syscall_from_line', 'RunStraced']

import sys
import re
from typing import Iterable, List, Optional, Tuple, Union

import dlb.fs
import dlb.ex
import dlb_contrib.backslashescape

assert sys.version_info >= (3, 7)

SYSCALL_NAME_REGEX = re.compile(rb'^(?P<name>[a-z][a-zA-Z0-9_#]*)')

# https://github.com/strace/strace/blob/v5.5/print_fields.h#L127
# https://github.com/strace/strace/blob/v5.5/util.c#L573
QUOTED_STRING_ARG_REGEX = re.compile(rb'^"(?P<value>([^"\\]|\\.)*)"')

SHORTENED_QUOTED_STRING_ARG_REGEX = re.compile(rb'^"([^"\\]|\\.)*"\.\.\.')

# https://github.com/strace/strace/blob/v5.5/print_fields.h#L233
# https://github.com/strace/strace/blob/v5.5/util.c#L539
FD_STRING_ARG_REGEX = re.compile(rb'^(0|[1-9][0-9]*)<(?P<value>([^<>"\\]|\\[^<>])*)>')

OTHER_ARG_REGEX = re.compile(rb'^[^,(){}\[\]"\\]+')


def _scan_argument_list(argument_list_str, closing_character):
    closing_by_opening = {ord('['): ord(']'), ord('{'): ord('}')}
    arguments = []
    rest = argument_list_str

    # strace/print_fields.h
    while True:
        if not rest:
            raise ValueError(f"missing {chr(closing_character)!r} in argument list")

        raw_argument = None
        potential_path_argument = None

        if rest[0] in closing_by_opening:
            raw_argument, r = _scan_argument_list(rest[1:], closing_by_opening[rest[0]])
            n = len(rest) - len(r)
            raw_argument = rest[:n]
            rest = rest[n:]
        else:
            for regex in [FD_STRING_ARG_REGEX, SHORTENED_QUOTED_STRING_ARG_REGEX, QUOTED_STRING_ARG_REGEX,
                          OTHER_ARG_REGEX]:
                m = regex.match(rest)
                if m:
                    raw_argument = m.group()
                    v = m.groupdict().get('value')
                    if v is not None:
                        try:
                            # https://github.com/strace/strace/blob/v5.5/util.c#L634
                            potential_path_argument = dlb_contrib.backslashescape.unquote(v, opening=None)
                        except ValueError:
                            raise ValueError(f"invalid quoting in argument: {raw_argument!r}") from None
                    rest = rest[len(raw_argument):]
                    break
            if raw_argument is None:
                raise ValueError(f"invalid argument: {rest!r}")

        arguments.append((raw_argument, potential_path_argument))

        if rest and rest[0] == closing_character:
            rest = rest[1:]
            break

        if rest[:1] != b',':
            raise ValueError(f"missing {chr(closing_character)!r} in argument list")

        rest = rest[1:].lstrip(b' ')

    return arguments, rest


# line from 'strace ...' or 'strace -y ...'
def syscall_from_line(line: bytes) -> Tuple[str, List[Optional[str]], List[bytes], bytes]:
    m = SYSCALL_NAME_REGEX.match(line)
    if not m:
        raise ValueError(f'not an strace line: {line!r}')
    name = m.group().decode()
    rest = line[len(name):]

    if not rest[:1] == b'(':
        raise ValueError(f'not an strace line: {line!r}')

    arguments, rest = _scan_argument_list(rest[1:], ord(')'))

    rest = rest.lstrip(b' ')
    if rest[:1] != b'=':
        raise ValueError(f'not an strace line: {line!r}')
    value = rest[1:].lstrip(b' ')

    string_and_fd_arguments = []  # e.g. '"a/b"' or '3</lib/x86_64-linux-gnu/libc-2.28.so>'
    other_arguments = []  # e.g. '{st_mode=S_IFDIR|0755, st_size=12288, ...}' or '0x7fffb28622d0 /* 39 vars */'
    encoding = sys.getfilesystemencoding()
    for raw, potential_path in arguments:
        if potential_path is None:
            other_arguments.append(raw)
        else:
            try:
                potential_path = potential_path.decode(encoding)
                string_and_fd_arguments.append(potential_path)
            except UnicodeDecodeError:
                string_and_fd_arguments.append(None)

    return name, string_and_fd_arguments, other_arguments, value


class RunStraced(dlb.ex.Tool):
    # Run dynamic helper with strace and return all successfully read files in the managed tree in *read_files*
    # and all successfully written files in the managed tree in *written_files*.
    #
    # Overwrite *EXECUTABLE* in subclass.

    # Dynamic helper, looked-up in the context.
    TRACING_EXECUTABLE = 'strace'

    # Command line parameters for *TRACING_EXECUTABLE* to output version information on standard output
    VERSION_PARAMETERS = ('-V',)

    # Dynamic helper of executable to  be traced by *TRACING_EXECUTABLE*, looked-up in the context.
    EXECUTABLE = ''  # define in subclass

    read_files = dlb.ex.input.RegularFile[:](explicit=False)
    written_files = dlb.ex.output.RegularFile[:](explicit=False)

    def get_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        # Return iterable of commandline arguments for *EXECUTABLE*.
        raise NotImplementedError

    async def redo(self, result, context):
        straced_helper = context.helper[self.EXECUTABLE]

        with context.temporary() as strace_output_file:
            await context.execute_helper(
                self.TRACING_EXECUTABLE,
                ['-y', '-e', 'trace=read,write', '-qq', '-o', strace_output_file, '--', straced_helper] +
                [c for c in self.get_arguments()])

            read_files = []
            checked_for_read_files = set()
            written_files = []
            checked_for_written_files = set()

            with open(strace_output_file.native, 'rb') as f:
                for line in f:
                    name, string_and_fd_arguments, other_arguments, value = syscall_from_line(line)
                    if name == 'read' and 'value' != b'0':
                        # SYS_FUNC(read): https://github.com/strace/strace/blob/v5.5/io.c#L16
                        try:
                            path = string_and_fd_arguments[0]
                        except IndexError:
                            raise ValueError(f"invalid strace output: {line!r}") from None
                        if path and path not in checked_for_read_files:
                            try:
                                read_files.append(context.working_tree_path_of(path, is_dir=False, existing=False))
                            except ValueError:
                                pass
                            checked_for_read_files.add(path)
                    elif name == 'write' and 'value' != b'0':
                        # SYS_FUNC(write): https://github.com/strace/strace/blob/v5.5/io.c#L31
                        try:
                            path = string_and_fd_arguments[0]
                        except IndexError:
                            raise ValueError(f"invalid strace output: {line!r}") from None
                        if path and path not in checked_for_written_files:
                            try:
                                written_files.append(context.working_tree_path_of(path, is_dir=False, existing=False))
                            except ValueError:
                                pass
                            checked_for_written_files.add(path)

            result.read_files = sorted(read_files)
            result.written_files = sorted(written_files)


# struct_sysent for system calls that match 'strace -e trace=%file ...':
#
#     %file -> TRACE_FILE: https://github.com/strace/strace/blob/v5.5/basic_filters.c#L152
#     TRACE_FILE -> TF:    https://github.com/strace/strace/blob/v5.5/sysent_shorthand_defs.h#L37
#
# https://github.com/strace/strace/blob/v5.5/syscall.c#L51:
#
#     const struct_sysent sysent0[] = {
#         #include "syscallent.h"
#     };
#
# https://github.com/strace/strace/blob/v5.5/sysent.h#L11:
#
#     typedef struct sysent {
#         unsigned nargs;
#         int sys_flags;
#         int sen;
#         int (*sys_func)();
#         const char *sys_name;
#     } struct_sysent;
#
# find . -name syscallent.h -exec grep -e '\bTF\b' {} \;
#
#     access
#     acct
#     chdir
#     chmod
#     chown
#     chown32
#     chroot
#     creat
#     execv
#     execve
#     execve#64
#     execveat
#     execveat#64
#     faccessat
#     fanotify_mark
#     fchmodat
#     fchownat
#     fstatat64
#     futimesat
#     getcwd
#     getxattr
#     inotify_add_watch
#     lchown
#     lchown32
#     lgetxattr
#     link
#     linkat
#     listxattr
#     llistxattr
#     lremovexattr
#     lsetxattr
#     lstat
#     lstat64
#     mkdir
#     mkdirat
#     mknod
#     mknodat
#     mount
#     name_to_handle_at
#     newfstatat
#     oldlstat
#     oldstat
#     oldumount
#     open
#     openat
#     osf_lstat
#     osf_old_lstat
#     osf_old_stat
#     osf_stat
#     osf_statfs
#     osf_statfs64
#     osf_utimes
#     pivot_root
#     quotactl
#     readlink
#     readlinkat
#     removexattr
#     rename
#     renameat
#     renameat2
#     rmdir
#     setxattr
#     stat
#     stat64
#     statfs
#     statfs64
#     statx
#     swapoff
#     swapon
#     symlink
#     symlinkat
#     truncate
#     truncate64
#     umount
#     umount2
#     unlink
#     unlinkat
#     uselib
#     uselib#64
#     utime
#     utimensat
#     utimes
