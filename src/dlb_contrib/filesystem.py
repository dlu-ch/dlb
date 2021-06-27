# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Manipulate sets of filesystem objects in an efficient and portable manner."""

# Usage example:
#
#   # "Atomically" collect a set of files in a directory with
#   # dlb_contrib.filesystem.FileCollector.
#
#   import dlb.ex
#   import dlb_contrib.filesystem
#
#   with dlb.ex.Context():
#       dlb_contrib.filesystem.FileCollector(
#           input_files=['build/out/application', 'build/out/doxygen/application.html.zip'],
#           output_directory='dist/'
#       ).start()
#       # replaces 'dist/' with a directory that contains the files
#       # 'dist/application.html', 'dist/application.html.zip'

__all__ = ['FileCollector', 'hardlink_or_copy']

import sys
import os
import stat
import shutil
import errno
from typing import Optional, Union

import dlb.ex

assert sys.version_info >= (3, 7)


def hardlink_or_copy(src: Union[str, os.PathLike], dst: Union[str, os.PathLike],
                     use_hard_link: Optional[bool] = None) -> bool:
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
    # Collect *input_files* in a directory *output_directory* as hardlinks or copies, removing the content of an
    # existing *output_directory* if it exists.
    #
    # Uses the last components of the paths in *input_files* as filenames in *output_directory*.
    #
    # Creates hardlinks for all files if the filesystem supports it and copies otherwise.
    # Is atomic in the following sense: *output_directory* contains exactly the files *input_files* (successful
    # completion), or does not exist, or is unchanged.
    #
    # Note: Do not use the created file system objects in *output_directory* as input or output dependencies
    # (only *output_directory* itself) of another tool instance. If you do, make sure assumption A-D2 is not violated.

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
