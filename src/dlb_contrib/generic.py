# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Add input dependencies to any tool instance."""

# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.generic
#
#   ...  # define ATool
#
#   with dlb.ex.Context():
#       check = dlb_contrib.generic.Check(input_files=['logo.png'])
#       ATool(...).run(force_redo=check.run())  # performs a redo of ATool(...) when 'logo.png' has changed

__all__ = ['Check']

import sys
import dlb.ex
assert sys.version_info >= (3, 7)


class Check(dlb.ex.Tool):
    # Make a redo (which does nothing) whenever an regular file or a directory changed.
    #
    # The result 'Check(...).run()' can be used like this to a add an input dependency on a group of other
    # input dependencies:
    #
    #    ATool().run(force_redo=Check(...).run())
    #
    # Note: It is more efficient to use the same Check() tool instance for multiple other tool instances
    # than adding its input dependencies to all of them.
    #
    # For GNU Make lovers: This is the equivalent to using a .PHONY target as a source.

    input_files = dlb.ex.Tool.Input.RegularFile[:]()
    input_directories = dlb.ex.Tool.Input.Directory[:]()

    async def redo(self, result, context):
        pass
