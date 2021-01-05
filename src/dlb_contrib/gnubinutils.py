# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Manipulate static libraries and ELF files with GNU Binutils."""

# GNU Binutils: <https://www.gnu.org/software/binutils/>
# Tested with: GNU Binutils for Debian 2.31.1
# Executable: 'ar'
#
# Usage example:
#
#   import dlb_contrib.gnubinutils
#
#   with dlb.ex.Context():
#       ...  # create 'a.o', 'b.o'
#       dlb_contrib.gnubinutils.Archive(
#           object_files=['a.o', 'b.o'],
#           archive_file='libexample.a'
#       ).start()

__all__ = ['Archive']

import sys
import os

import dlb.ex

assert sys.version_info >= (3, 7)


class Archive(dlb.ex.Tool):
    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'ar'

    # Command line parameters for *EXECUTABLE* to output version information on standard output
    VERSION_PARAMETERS = ('--version',)

    # String of operation modifiers for operation 'r' (each modifier is a ASCII letter).
    OPERATION_MODIFIERS = ''

    object_files = dlb.ex.input.RegularFile[1:]()
    archive_file = dlb.ex.output.RegularFile(replace_by_same_content=False)

    async def redo(self, result, context):
        with context.temporary() as archive_file:
            os.unlink(archive_file.native)
            await context.execute_helper(
                self.EXECUTABLE,
                ['-r' + self.OPERATION_MODIFIERS, archive_file] + [p for p in result.object_files])
            context.replace_output(result.archive_file, archive_file)
