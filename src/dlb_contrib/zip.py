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
                files = content_directory.list_r(recurse_name_filter='', follow_symlinks=False)
                for f in files:
                    native_path = str((content_directory / f).native)
                    if os.path.isfile(native_path):
                        z.write(native_path, arcname=f.as_string())

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
