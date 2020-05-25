# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Group or combine multiple tool instances or tool classes."""

# Usage example:
#
#   # Request a redo tool instance based on a dynamic condition with
#   # dlb_contrib.generic.Check.
#
#   import dlb.ex
#   import dlb_contrib.generic
#
#   with dlb.ex.Context():
#       # request a redo (no redo miss even if condition cannot be
#       # reproduced in the next run)
#       problem_detected = ....
#
#       needs_update = dlb_contrib.generic.Check(
#           result_file='build/out/result.uptodate'
#       ).start(force_redo=problem_detected)
#       # performs redo if *result_file* this does not exist; redo removes *result_file*
#
#       with dlb.ex.Context:  # waits for previous redos to complete
#           if needs_update:
#               # perform actual work
#               # *needs_update* will be True next time if this fails with an exception
#               ...
#
#       needs_update.result_file.native.raw.touch()  # mark successful completion
#
# Usage example:
#
#   # Before checking dependencies in detail, check necessary precondition for redo with
#   # dlb_contrib.generic.Check:
#   # Check the source code dependencies of a huge library only if at least one file in
#   # the source code directory has changed (much faster if no changes).
#
#   import dlb.ex
#   import dlb_contrib.generic
#
#   with dlb.ex.Context():
#       # contains all source files of a huge library:
#       library_source_directory = dlb.fs.Path('src/libx/')
#       archive_file = dlb.fs.Path(...)
#
#       # update mtime of directory if content has later mtime
#       # (requires monotonic system time to detect all mtime changes)
#       mtime = dlb.fs.propagate_mtime(library_source_directory)
#       assert mtime is None or mtime <= dlb.ex.Context.active.working_tree_time_ns
#
#       # 1. check fast but course whether a update may be necessary
#       needs_update = dlb_contrib.generic.Check(
#           input_directories=[library_source_directory],
#           output_files=[archive_file]
#           result_file=archive_file.with_appended_suffix('.uptodate')
#               # redo if this does not exist
#       ).start()  # redo removes *result_file*
#
#       with dlb.ex.Context:  # waits for previous redos to complete
#           if needs_update:  # need to take a closer look?
#               # 2. check in detail and perform actual work if necessary
#               # *needs_update* will be True next time if this fails with an exception
#               ...
#
#       needs_update.result_file.native.raw.touch()  # mark successful completion
#
# Usage example:
#
#   # Query the version of executables used by tool classes with
#   # dlb_contrib.generic.VersionQuery.
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

__all__ = ['Check', 'VersionQuery', 'VERSION_WORD_REGEX']

import sys
import re
from typing import Dict, Optional, Tuple

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
