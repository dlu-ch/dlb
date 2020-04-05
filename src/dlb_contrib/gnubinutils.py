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
#     import dlb_contrib.gnubinutils
#
#     with dlb.ex.Context():
#         ...  # create 'a.o', 'b.o'
#         dlb_contrib.gnubinutils.Archive(
#               object_files=['a.o', 'b.o'],
#               archive_file='libexample.a').run()

__all__ = ['Archive']

import os
import dlb.ex


class Archive(dlb.ex.Tool):
    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'ar'

    # String of operation modifiers for operation 'r' (each modifier is a ASCII letter).
    OPERATION_MODIFIERS = ''

    object_files = dlb.ex.Tool.Input.RegularFile[1:]()
    archive_file = dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False)

    async def redo(self, result, context):
        with context.temporary() as archive_file:
            os.unlink(archive_file.native)
            await context.execute_helper(
                self.EXECUTABLE,
                ['-r' + self.OPERATION_MODIFIERS, archive_file] + [p for p in result.object_files])
            context.replace_output(result.archive_file, archive_file)