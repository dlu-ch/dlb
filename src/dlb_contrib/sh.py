# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Run commands with the POSIX sh shell - the standard command language interpreter."""

# sh: <https://pubs.opengroup.org/onlinepubs/9699919799/utilities/sh.html>
# Executable: 'sh'
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.sh
#
#   class PrintString(dlb_contrib.sh.ShScriptlet):
#       SCRIPTLET = "echo echoed: " + dlb_contrib.sh.quote('a $ is a $')
#
#   with dlb.ex.Context():
#       ... = PrintString().start().processed_output.decode()  # 'echoed: a $ is a $\n'

__all__ = ['quote', 'ShScriptlet']

import sys
import textwrap
from typing import Iterable, Optional, Union

import dlb.fs
import dlb.ex

assert sys.version_info >= (3, 7)


def quote(text: str) -> str:
    # Quote an arbitrary string such that it keeps it literal meaning when evaluated by sh
    return "'" + text.replace("'", "'\\''") + "'"


class ShScriptlet(dlb.ex.Tool):
    # Run a small sh script, wait for its completion and return its output to stdout as a string.
    # Do not use this for "big" scripts with a lot of output.
    #
    # Overwrite *SCRIPTLET* in subclass.

    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'sh'

    NAME = 'scriptlet'
    SCRIPTLET = ''  # this will be executed by sh - overwrite in subclass

    processed_output = dlb.ex.output.Object(explicit=False)

    # Overwrite this to chunk processor if you want to process the output incrementally.
    # See dlb.ex.RedoContext.execute_helper_with_output() for details.
    def get_chunk_processor(self) -> Optional[dlb.ex.ChunkProcessor]:
        return None

    def get_scriptlet_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return []

    async def redo(self, result, context):
        script = '\n'.join(textwrap.dedent(self.SCRIPTLET).strip().splitlines())
        processor = self.get_chunk_processor()
        _, processed_output = await context.execute_helper_with_output(
            self.EXECUTABLE, ['-c', '-', script, self.NAME] + [c for c in self.get_scriptlet_arguments()],
            chunk_processor=processor)
        result.processed_output = processed_output
