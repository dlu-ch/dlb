# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Add input dependencies to any tool instance."""

# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.generic
#
#   class ATool(dlb.ex.Tool):
#       ...
#
#   with dlb.ex.Context():
#       check = dlb_contrib.generic.Check(input_files=['logo.png'])
#       ATool(...).run(force_redo=check.run())
#       # performs a redo of ATool(...) if 'logo.png' has changed
#
#   ...
#
#   with dlb.ex.Context():
#       # contains all source files of a huge library:
#       library_source_directory = dlb.fs.Path('src/libx/')
#       archive_file = dlb.fs.Path(...)  # compiled from *library_source_directory*
#
#       # 1. check if update of *archive_file* may be necessary - fast but coarse
#       with dlb.ex.Context:
#           # update mtime of directory if content has later mtime
#           # (requires monotonic system time to detect all mtime changes)
#           mtime = dlb.fs.propagate_mtime(library_source_directory)
#           assert mtime is None or mtime <= dlb.ex.Context.active.working_tree_time_ns
#
#           needs_update = dlb_contrib.generic.ResultRemover(
#               result_file=archive_file.with_appended_suffix('.uptodate')
#           ).run(
#               force_redo=dlb_contrib.generic.Check(
#                   input_directories=[library_source_directory],
#                   output_files=[archive_file]
#               ).run()
#           )
#           # after normal exit from this context, needs_update.result_file does not exist
#           # if bool(needs_update) is True
#
#       if needs_update:
#           # 2. compile library to *archive_file* - slow but fine
#           # (*needs_update* will be True next time if this fails)
#           ...
#           needs_update.result_file.native.raw.touch()  # mark successfull completion

__all__ = ['Check', 'ResultRemover']

import sys
import dlb.ex

assert sys.version_info >= (3, 7)


class Check(dlb.ex.Tool):
    # Make a redo (which does nothing) when one of the given regular files or directories has changed.
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

    input_files = dlb.ex.input.RegularFile[:](required=False)
    input_directories = dlb.ex.input.Directory[:](required=False)
    output_files = dlb.ex.output.RegularFile[:](required=False)
    output_directories = dlb.ex.output.Directory[:](required=False)

    async def redo(self, result, context):
        pass


class ResultRemover(dlb.ex.Tool):
    # Remove *result_file* (but make sure its directory exists) at every redo.
    # See above for a usage example.

    result_file = dlb.ex.output.RegularFile()

    async def redo(self, result, context):
        p = context.root_path / result.result_file
        p[:-1].native.raw.mkdir(parents=True, exist_ok=True)
        try:
            p.native.raw.unlink()
        except FileNotFoundError:
            pass
