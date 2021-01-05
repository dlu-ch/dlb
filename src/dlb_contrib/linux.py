# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Query Linux-specific information on hardware, filesystems and operating system as exposed by /proc."""

# /proc of Linux: <https://man7.org/linux/man-pages/man5/proc.5.html>
# Source code of Linux 4.19: <https://github.com/torvalds/linux/tree/v4.19>
# Tested with: Linux 4.19.0-9-amd64 #1 SMP Debian 4.19.118-2 (2020-04-29) x86_64 GNU/Linux
#
# Usage example:
#
#   # Get system information as provided by the Linux kernel.
#
#   import dlb_contrib.linux
#
#   kernel_info = dlb_contrib.linux.get_kernel_info(['.'])
#   # e.g. ('Linux', '4.19.0-9-amd64', '#1 SMP Debian 4.19.118-2 (2020-04-29)')
#
#   total_usable, estimated_available_without_swapping = \
#       dlb_contrib.linux.get_memory_info()
#       # e.g. (16694640640, 13603610624)
#
#   cache_sizes = dlb_contrib.linux.get_cpu_info().by_key('cache size')
#   # e.g. {'8192 KB': (0, 1, 2, 3, 4, 5, 6, 7)}
#
# Usage example:
#
#   # List filesystems whose mountpoints are a prefix of os.path.realpath('.').
#
#   import dlb_contrib.linux
#
#   vfstype_name_by_mountpoint = \
#       dlb_contrib.backslashescape.get_mounted_filesystems(['.'])
#       # e.g. {Path('/'): 'xfs', Path('/tmp/'): 'tmpfs'}

__all__ = ['KEY_VALUE_LINE_REGEX', 'get_kernel_info', 'get_memory_info', 'get_cpu_info', 'get_mounted_filesystems']

import re
import os
from typing import Dict, Iterable, Optional, Sequence, Tuple

import dlb.fs
import dlb_contrib.backslashescape


KEY_VALUE_LINE_REGEX = re.compile(rb'\A(?P<key>\S+(?: \S+)*)[ \t]*: *(?P<value>\S.*)?\n\Z')

PROC_ROOT_DIRECTORY = dlb.fs.Path('/proc/')


def _get_limited_text(source_path: dlb.fs.PathLike, max_size: int) -> bytes:
    max_size = max(1, max_size)
    source_path = dlb.fs.Path(source_path)
    with open(source_path.native, 'rb') as f:
        line = f.read(max_size + 1)
        if line[-1:] != b'\n':
            raise RuntimeError(f"does not end with '\\n' (too large?): {source_path.as_string()!r}")
        return line


def _split_key_value_line(line) -> Tuple[str, Optional[str]]:
    m = KEY_VALUE_LINE_REGEX.fullmatch(line)
    if not m:
        raise RuntimeError(f'unexpected key-value line: {line!r}')
    v = m.group('value')
    return m.group('key').decode(), v.decode() if v else v


def get_kernel_info(*, proc_root_directory: dlb.fs.PathLike = PROC_ROOT_DIRECTORY, max_size: int = 16 * 2 ** 10) \
        -> Tuple[str, str, str]:
    # Return identification of the running Linux kernel (version and build information).

    proc_root_directory = dlb.fs.Path(proc_root_directory)

    def get_info(p):
        return _get_limited_text(proc_root_directory / 'sys/kernel/' / p, max_size).strip().decode()

    # https://man7.org/linux/man-pages/man5/proc.5.html
    return get_info('ostype'), get_info('osrelease'), get_info('version')


def get_memory_info(*, proc_root_directory: dlb.fs.PathLike = PROC_ROOT_DIRECTORY) -> Tuple[int, int]:
    # Return information on available RAM.

    proc_root_directory = dlb.fs.Path(proc_root_directory)
    meminfo_file = proc_root_directory / 'meminfo'

    d = {}
    with open(meminfo_file.native, 'rb') as f:
        for line in f:
            key, value = _split_key_value_line(line)
            if key in ('MemTotal', 'MemAvailable') and value:
                if not value.endswith(' kB'):  # is kiB, actually
                    raise RuntimeError(f'{key!r} in {meminfo_file.as_string()!r} has unexpected value: {value!r}')
                d[key] = int(value[:-3], 10) * 2**10

    try:
        total_usable, estimated_available_without_swapping = d['MemTotal'], d['MemAvailable']
    except KeyError as e:
        raise RuntimeError(f"missing key in {meminfo_file.as_string()!r}: {e.args[0]!r}")

    # https://man7.org/linux/man-pages/man5/proc.5.html
    #
    #    total_usable:
    #        Total usable RAM (i.e., physical RAM minus a few reserved bits and the kernel binary code).
    #
    #    estimated_available_without_swapping:
    #        An estimate of how much memory is available for starting new applications, without swapping.

    return total_usable, estimated_available_without_swapping  # in byte


class CpuInfo:
    # Each CPU is identified with a non-negative index < *self.cpu_count* and is described by key-value pairs.
    # Example for key-value pair: key: 'vendor_id', value: 'GenuineIntel'.
    # The keys are completely architecture specific. There is no set of key that is present on all architectures
    # (except maybe 'processor').

    def __init__(self, cpu_infos: Sequence[Dict[str, Optional[str]]]):
        cpu_infos = tuple(i for i in cpu_infos)

        cpu_indices_by_value_by_key: Dict[str, Dict[Optional[str], Tuple[int, ...]]] = {}
        for cpu_indices, cpu_info in enumerate(cpu_infos):
            for key, value in cpu_info.items():
                d = cpu_indices_by_value_by_key.get(key, {})
                d[value] = d.get(value, ()) + (cpu_indices,)
                cpu_indices_by_value_by_key[key] = d

        value_by_key_by_maximum_cpu_index_set: Dict[Tuple[int, ...], Dict[str, Optional[str]]] = {}
        for key, cpu_indices_by_value in cpu_indices_by_value_by_key.items():
            for value, cpu_indices in cpu_indices_by_value.items():  # all *value* and all *cpu_indices* are different
                d = value_by_key_by_maximum_cpu_index_set.get(cpu_indices, {})
                d[key] = value
                value_by_key_by_maximum_cpu_index_set[cpu_indices] = d

        self._cpu_infos = cpu_infos
        self._cpu_indices_by_value_by_key = cpu_indices_by_value_by_key
        self._value_by_key_by_maximum_cpu_index_set = value_by_key_by_maximum_cpu_index_set
        self._maximum_cpu_index_sets = \
            tuple(sorted(self._value_by_key_by_maximum_cpu_index_set, key=lambda k: (-len(k), k)))

    @property
    def cpu_count(self) -> int:
        # (Non-negative) number of CPUs.
        # Each non-negative integer smaller than this is a valid CPU index.
        return len(self._cpu_infos)

    @property
    def maximum_cpu_index_sets(self) -> Tuple[Tuple[int]]:
        # Sets of CPU indices with common key-value pairs as sorted tuples, the ones with the most members first.
        # For each member *s* of the return value, self[s] is not empty.
        return self._maximum_cpu_index_sets

    def by_key(self, key: str) -> Dict[Optional[str], Tuple[int, ...]]:
        # Return a dictionary of CPU indices by value for *key*.
        return self._cpu_indices_by_value_by_key[key]

    def by_cpu_index(self, cpu_index: int) -> Dict[str, Optional[str]]:
        # Return a dictionary of all key-value pairs for the CPU with CPU index *cpu_index*.
        return self._cpu_infos[cpu_index]

    def by_maximum_cpu_index_set(self, maximum_cpu_index_set: Iterable[int]) -> Dict[str, Optional[str]]:
        # Return a dictionary of all key-value pairs for which *cpu_indices* forms the largest set of CPU indices
        # with these key-value pairs.
        # Use *self.sorted_cpu_indices* to get all such sets.
        maximum_cpu_index_set = tuple(sorted(frozenset(maximum_cpu_index_set)))
        return self._value_by_key_by_maximum_cpu_index_set.get(maximum_cpu_index_set, {})

    def __repr__(self) -> str:
        sorted_dicts = [self._value_by_key_by_maximum_cpu_index_set[i] for i in self._maximum_cpu_index_sets]
        s = ', '.join(f'{k}: {v!r}' for k, v in zip(self._maximum_cpu_index_sets, sorted_dicts))
        return f'{self.__class__.__qualname__}({{{s}}})'


def get_cpu_info(*, proc_root_directory: dlb.fs.PathLike = PROC_ROOT_DIRECTORY) -> CpuInfo:

    proc_root_directory = dlb.fs.Path(proc_root_directory)

    # /proc/cpuinfo:
    #   https://github.com/torvalds/linux/blob/v4.19/fs/proc/cpuinfo.c#L19
    #   https://github.com/torvalds/linux/blob/v4.19/fs/proc/cpuinfo.c#L13
    #   -> cpuinfo_open() -> cpuinfo_op
    #
    #  cpuinfo_op:
    #     architecture-specific, linux/arch/*/kernel/cpu/*.c,
    #     https://github.com/search?q=%22const+struct+seq_operations+cpuinfo_op%22+repo%3Atorvalds%2Flinux+extension%3A.c+language%3AC&type=Code
    #     https://github.com/torvalds/linux/blob/v4.19/arch/x86/kernel/cpu/proc.c#L162
    #     https://github.com/torvalds/linux/blob/v4.19/arch/riscv/kernel/cpu.c#L79
    #     -> not a single common key between x86 and riscv!

    meminfo_file = proc_root_directory / 'cpuinfo'

    cpu_info = {}
    cpu_infos = []

    with open(meminfo_file.native, 'rb') as f:
        for line in f:
            if line == b'\n':
                if cpu_info:
                    cpu_infos.append(cpu_info)
                    cpu_info = {}
            else:
                key, value = _split_key_value_line(line)
                cpu_info[key] = value  # last one wins
        if cpu_info:
            cpu_infos.append(cpu_info)

    return CpuInfo(cpu_infos)


def get_mounted_filesystems(contained_paths: Optional[Iterable[dlb.fs.PathLike]] = None, *,
                            proc_root_directory: dlb.fs.PathLike = PROC_ROOT_DIRECTORY) -> Dict[dlb.fs.Path, str]:
    # Return mountpoint (absolute path) and name of filesystem type (e.g. 'xfs') for all mounted filesystems according
    # to *source_path*.
    # If *contained_paths* is not empty, all filesystems whose mountpoint is not a prefix of a os.path.realpath(p)
    # for any member of *contained_paths*.

    # /proc/mounts, /proc/self/mounts:
    #   https://man7.org/linux/man-pages/man5/proc.5.html:
    #     [...] lists the mount points of the process's own mount namespace
    #     [...] is documented in fstab(5).
    #   https://man7.org/linux/man-pages/man5/fstab.5.html:

    # source code of Linux 4.19:
    #
    #   /proc/self/mounts
    #     https://github.com/torvalds/linux/blob/v4.19/fs/proc_namespace.c#L318
    #     https://github.com/torvalds/linux/blob/v4.19/fs/proc_namespace.c#L303
    #     -> mounts_open() -> show_vfsmnt()
    #
    #     show_vfsmnt():
    #       https://github.com/torvalds/linux/blob/v4.19/fs/proc_namespace.c#L97
    #       -> mangle(), __d_path(), seq_path_root(..., " \t\n\\"), sb->s_op->show_devname()
    #
    #       mangle():
    #         https://github.com/torvalds/linux/blob/v4.19/fs/proc_namespace.c#L83
    #         https://github.com/torvalds/linux/blob/v4.19/fs/seq_file.c#L375
    #         https://github.com/torvalds/linux/blob/v4.19/include/linux/string_helpers.h#L63
    #         https://github.com/torvalds/linux/blob/v4.19/lib/string_helpers.c#L493
    #         https://github.com/torvalds/linux/blob/v4.19/lib/string_helpers.c#L395
    #         -> seq_escape(..., " \t\n\\")  > string_escape_str(..., ESCAPE_OCTAL, esc)
    #         -> string_escape_str(..., ESCAPE_OCTAL, esc) -> string_escape_mem(..., ESCAPE_OCTAL, esc)
    #         -> escape_octal() -> "\\ooo"
    #
    #       __d_path():
    #         https://github.com/torvalds/linux/blob/v4.19/fs/d_path.c#L174
    #
    #       seq_path_root(..., esc):
    #         https://github.com/torvalds/linux/blob/v4.19/Documentation/filesystems/seq_file.txt#L220
    #         https://github.com/torvalds/linux/blob/v4.19/fs/seq_file.c#L489
    #         https://github.com/torvalds/linux/blob/v4.19/fs/seq_file.c#L422
    #         -> mangle_path(..., esc)  -> "\\ooo"
    #
    # Summary:
    #
    #   - Each line of /proc/self/mounts consists of exactly 6 fields, separated by a single space character.
    #   - A field may contain any ASCII characters except space, HT, LF, and \, which are escaped as "\\ooo",
    #     where ooo is a three-digit octal representation of the the ASCII code.
    #   - The first field (device) may be filesystem specific and may be "none".
    #   - The second field (mount point) is an path formatted by seq_path_root().

    proc_root_directory = dlb.fs.Path(proc_root_directory)
    vfstype_name_by_mountpoint = {}

    if contained_paths:
        contained_paths = [os.path.realpath(dlb.fs.Path(p).native) for p in contained_paths]

    mounts_file = proc_root_directory / 'self/mounts'
    with open(mounts_file.native, 'rb') as f:
        for line in f:  # split onle by b'\n'; https://docs.python.org/3/library/io.html#io.IOBase.readline
            try:
                _, mountpoint, vfstype_name, _, _, _ = line.rstrip().split(b' ')  # ValueError if corrupt
                mountpoint = dlb_contrib.backslashescape.unquote_octal(mountpoint)
            except ValueError:
                raise RuntimeError(f'unexpected line in {mounts_file.as_string()!r}: {line!r}') from None

            mountpoint = os.fsdecode(mountpoint)
            if os.path.isabs(mountpoint):  # not 'none'
                vfstype_name = vfstype_name.decode('ascii')

                ignore = False
                if contained_paths:
                    if not os.path.isdir(mountpoint) or os.path.realpath(mountpoint) != mountpoint:
                        raise RuntimeError(f'not a real path: {mountpoint!r}')
                    if not any(os.path.commonpath([os.path.realpath(p), mountpoint]) == mountpoint
                               for p in contained_paths):
                        ignore = True

                if not ignore:
                    # last one wins
                    vfstype_name_by_mountpoint[dlb.fs.Path(dlb.fs.Path.Native(mountpoint), is_dir=True)] = vfstype_name

    return vfstype_name_by_mountpoint
