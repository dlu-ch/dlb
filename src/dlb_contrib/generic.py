# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Add input dependencies to any tool instance."""

# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.generic
#
#   with dlb.ex.Context():
#       # contains all source files of a huge library:
#       library_source_directory = dlb.fs.Path('src/libx/')
#       archive_file = dlb.fs.Path(...)  # compiled from *library_source_directory*
#
#       # 1. check if update of *archive_file* may be necessary - fast but coarse
#       # update mtime of directory if content has later mtime
#       # (requires monotonic system time to detect all mtime changes)
#       mtime = dlb.fs.propagate_mtime(library_source_directory)
#       assert mtime is None or mtime <= dlb.ex.Context.active.working_tree_time_ns
#
#       needs_update = dlb_contrib.generic.Check(
#           input_directories=[library_source_directory],
#           output_files=[archive_file]
#           result_file=archive_file.with_appended_suffix('.uptodate')
#               # redo if this does not exist
#       ).start()  # redo removes *result_file*
#
#       with dlb.ex.Context:  # waits for previous redos to complete
#           if needs_update:  # need to take a closer look?
#               # 2. compile library to *archive_file* - slow but fine
#               # *needs_update* will be True next time if this fails with an exception
#               ...
#
#       needs_update.result_file.native.raw.touch()  # mark successful completion
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.generic
#
#   with dlb.ex.Context():
#       class VersionQuery(dlb_contrib.generic.VersionQuery):
#           VERSION_PARAMETERS_BY_EXECUTABLE = {
#               tool.EXECUTABLE: tool.VERSION_PARAMETERS
#               for tool in [dlb_contrib.gcc.CCompilerGcc, dlb_contrib.doxygen.Doxygen, ...]
#           }
#       version_by_path = VersionQuery().start().version_by_path
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.generic
#
#   with dlb.ex.Context():
#       dlb_contrib.generic.FileCollector(
#           input_files=['build/out/application', 'build/out/doxygen/application.html.zip'],
#           output_directory='dist/'
#       ).start()
#       # replaces 'dist/' with a directory that contains the files
#       # 'dist/application.html', 'dist/application.html.zip'

__all__ = ['Check', 'VersionQuery', 'FileCollector', 'VERSION_WORD_REGEX', 'hardlink_or_copy']

import sys
import re
import os
from typing import Dict, Optional, Tuple, Union

import dlb.ex

assert sys.version_info >= (3, 7)

# e.g. 'v1.2.3-alpha4'
VERSION_WORD_REGEX = re.compile(br'(?:^|\s)(?P<version>[0-9a-zA-Z._@+-]*[0-9]\.[0-9][0-9a-zA-Z._@+-]*)(?:\s|$)')


class Check(dlb.ex.Tool):
    # Perform a redo (which does nothing) when one of the given regular files or directories has changed
    # or one of the given output files does not exist.
    #
    # Remove *result_file* (but make sure its directory exists) at every redo if given.
    #
    # See above for an example.
    #
    # For GNU Make lovers: This is the equivalent to using a .PHONY target as a source.

    input_files = dlb.ex.input.RegularFile[:](required=False)
    input_directories = dlb.ex.input.Directory[:](required=False)
    output_files = dlb.ex.output.RegularFile[:](required=False)
    output_directories = dlb.ex.output.Directory[:](required=False)

    result_file = dlb.ex.output.RegularFile(required=False)

    async def redo(self, result, context):
        if result.result_file is not None:
            p = context.root_path / result.result_file
            p[:-1].native.raw.mkdir(parents=True, exist_ok=True)
            try:
                p.native.raw.unlink()
            except FileNotFoundError:
                pass


class VersionQuery(dlb.ex.Tool):
    # Execute dynamic helpers to query their version.
    # Overwrite *VERSION_PARAMETERS_BY_EXECUTABLE* in a subclass *C* and then use 'C().start().version_by_path'.

    # Dictionary of commandline parameters by executable.
    # Example: {dlb_contrib.tex.Latex.EXECUTABLE: dlb_contrib.tex.Latex.VERSION_PARAMETERS}.
    VERSION_PARAMETERS_BY_EXECUTABLE: Dict[str, Tuple[str]] = {}

    # Dictionary of versions of all executables in *VERSION_PARAMETERS_BY_EXECUTABLE*.
    #
    # The key is the absolute path of the executable *e* where *e* is a key of *VERSION_PARAMETERS_BY_EXECUTABLE*.
    # The value is the first version word in the first non-empty line (after removing white space) in *e*'s
    # output to standard output when called with command line parameters VERSION_PARAMETERS_BY_EXECUTABLE[e].
    #
    # A version word is a word (delimited by whitespace or beginning/end of line) that contains two decimal digits
    # separated by '.' and consists only of ASCII letters, decimal digits, '_', '.', '+', '-', '@'.
    # Example: 'v1.2.3-alpha4'.
    version_by_path = dlb.ex.output.Object(explicit=False)

    async def redo(self, result: 'dlb.ex.RunResult', context: 'dlb.ex.RedoContext') -> Optional[bool]:
        version_by_path = {}

        for executable, version_parameters in sorted(self.VERSION_PARAMETERS_BY_EXECUTABLE.items()):
            first_line = None
            version = None
            _, output = await context.execute_helper_with_output(executable, [p for p in version_parameters])
            for li in output.splitlines():
                li = li.strip()
                if li:
                    first_line = li
                    break
            m = VERSION_WORD_REGEX.search(first_line)
            if m:
                version = m.group('version').decode()
            version_by_path[context.helper[executable]] = version

        result.version_by_path = version_by_path
        return True


def hardlink_or_copy(src: Union[str, os.PathLike], dst: Union[str, os.PathLike],
                     use_hard_link: Optional[bool] = None) -> bool:
    import stat
    import shutil
    import errno

    sr = os.lstat(src)
    if not stat.S_ISREG(sr.st_mode) or stat.S_ISLNK(sr.st_mode):
        raise RuntimeError(f'not a regular file: {src!r}')

    if use_hard_link or use_hard_link is None:
        try:
            # on FAT32: "OSError: [Errno 1] Operation not permitted" -> EPERM -> PermissionError
            os.link(src=src, dst=dst)
            use_hard_link = True
        except PermissionError as e:
            if use_hard_link or e.errno != errno.EPERM:
                raise
            use_hard_link = False

    if not use_hard_link:
        shutil.copyfile(src=src, dst=dst)

    return use_hard_link


class FileCollector(dlb.ex.Tool):
    # Collect *input_files* in a directory as hardlinks or copies.
    # The last components of the paths in *input_files* are used as filenames in *output_directory*.
    #
    # Creates hardlinks for all files if the filesystem supports it and copies otherwise.
    # Is atomic in the following sense: *output_directory* contains exactly the files *input_files* (successful
    # completion), or does not exist, or is unchanged.

    input_files = dlb.ex.input.RegularFile[:]()
    output_directory = dlb.ex.output.Directory()

    async def redo(self, result, context):
        path_by_file_name = {}
        for input_file in result.input_files:
            file_name = input_file.components[-1]
            if file_name in path_by_file_name:
                p = path_by_file_name[file_name]
                msg = (
                    f"'input_files' contains multiple members with same file name: "
                    f"{p.as_string()!r} and {input_file.as_string()!r}"
                )
                raise ValueError(msg)
            path_by_file_name[file_name] = input_file

        # create read-only hard link in *output_directory* for each member of *input_files*
        with context.temporary(is_dir=True) as output_directory:
            use_hard_links = None  # detect hardlink support with first file

            for input_file in result.input_files:  # preserve order
                output_file = output_directory / input_file.components[-1]
                use_hard_links = hardlink_or_copy(src=input_file.native, dst=output_file.native,
                                                  use_hard_link=use_hard_links)

            context.replace_output(result.output_directory, output_directory)
