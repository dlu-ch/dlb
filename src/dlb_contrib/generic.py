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
#           needs_update.result_file.native.raw.touch()  # mark successful completion
#
#   ...
#
#   with dlb.ex.Context():
#       class VersionQuery(dlb_contrib.generic.VersionQuery):
#           VERSION_PARAMETERS_BY_EXECUTABLE = {
#               tool.EXECUTABLE: tool.VERSION_PARAMETERS
#               for tool in [dlb_contrib.gcc.CCompilerGcc, dlb_contrib.doxygen.Doxygen, ...]
#           }
#       version_by_path = VersionQuery().run().version_by_path

__all__ = ['Check', 'ResultRemover', 'VersionQuery', 'VERSION_WORD_REGEX']

import sys
import re
from typing import Dict, Optional, Tuple

import dlb.ex

assert sys.version_info >= (3, 7)

# e.g. 'v1.2.3-alpha4'
VERSION_WORD_REGEX = re.compile(b'(^|\s)(?P<version>[0-9a-zA-Z._@+-]*[0-9]\.[0-9][0-9a-zA-Z._@+-]*)($|\s)')

# TODO replace (prone to redo miss when dlb aborted between Check(...).run() and use of result
class Check(dlb.ex.Tool):
    # Perform a redo (which does nothing) when one of the given regular files or directories has changed
    # or one of the given output files does not exist.
    #
    # The result 'Check(...).run()' can be used like this to a add an input dependency on a group of other
    # input dependencies:
    #
    #    ATool().run(force_redo=Check(...).run())
    #
    # Notes:
    #
    #   - It is more efficient to use the same Check() tool instance for multiple other tool instances
    #     than adding its input dependencies to all of them.
    #   - Should only be used in conjunction with ResultRemover to avoid redo misses;
    #     a redo miss can occur when dlb is aborted between 'Check(...).run()' and the use of its result like
    #     'ATool().run(force_redo=...)'
    #
    # For GNU Make lovers: This is the equivalent to using a .PHONY target as a source.

    input_files = dlb.ex.input.RegularFile[:](required=False)
    input_directories = dlb.ex.input.Directory[:](required=False)
    output_files = dlb.ex.output.RegularFile[:](required=False)
    output_directories = dlb.ex.output.Directory[:](required=False)

    async def redo(self, result, context):
        pass


# TODO remove
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


class VersionQuery(dlb.ex.Tool):
    # Execute dynamic helpers to query their version.
    # Overwrite *VERSION_PARAMETERS_BY_EXECUTABLE* in a subclass *C* and then use 'C().run().version_by_path'.

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
