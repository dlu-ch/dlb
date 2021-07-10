# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Create ZIP archives from directory content."""

# .ZIP file format: <https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT>
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.zip
#
#   with dlb.ex.Context():
#       dlb_contrib.zip.ZipDirectory(
#           content_directory='build/out/html/',
#           archive_file='build/out/application.html.zip'
#       ).start()

__all__ = ['ZipDirectory']

import sys
import os.path
import zipfile

import dlb.ex

assert sys.version_info >= (3, 7)


class ZipDirectory(dlb.ex.Tool):
    COMPRESSION = zipfile.ZIP_BZIP2
    COMPRESS_LEVEL = 9

    # Include a directory entry for each path that is a prefix of the path of a contained file?
    INCLUDE_PREFIX_DIRECTORIES = True

    # The regular files in this directory (with all its subdirectories) build the content of the archive.
    # Symbolic links are not followed.
    # Filesystem that are no directories or regular files are ignored.
    content_directory = dlb.ex.input.Directory()

    archive_file = dlb.ex.output.RegularFile(replace_by_same_content=False)

    async def redo(self, result, context):
        with context.temporary() as archive_file:
            content_directory = result.content_directory
            if not content_directory.is_absolute():
                content_directory = context.root_path / content_directory

            with zipfile.ZipFile(archive_file.native, 'w', compression=self.COMPRESSION,
                                 compresslevel=self.COMPRESS_LEVEL) as z:
                regular_files = [
                    p for p in content_directory.list_r(recurse_name_filter='', follow_symlinks=False)
                    if os.path.isfile(str((content_directory / p).native))
                ]

                containing_directories = set()

                if self.INCLUDE_PREFIX_DIRECTORIES:

                    for p in regular_files:
                        while True:
                            p = p[:-1]
                            if not p.parts:
                                break
                            if p in containing_directories:
                                break
                            containing_directories.add(p)

                for p in sorted(containing_directories) + regular_files:
                    z.write((content_directory / p).native, arcname=p.as_string())

            # For zipimport on MSYS2, adding directories to the archive seems to be necessary

            # https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT:
            #
            #     4.4.17.1 The name of the file, with optional relative path.
            #     The path stored MUST NOT contain a drive or
            #     device letter, or a leading slash.  All slashes
            #     MUST be forward slashes '/' as opposed to
            #     backwards slashes '\' for compatibility with Amiga
            #     and UNIX file systems etc.  If input came from standard
            #     input, there is no file name field.

            context.replace_output(result.archive_file, archive_file)
