# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Support of the Posix sh shell - the standard command language interpreter."""

import sys
import subprocess
import textwrap
from typing import Iterable, Union
import dlb.fs
import dlb.ex
assert sys.version_info >= (3, 7)


# https://pubs.opengroup.org/onlinepubs/9699919799/utilities/sh.html
class ShScriptlet(dlb.ex.Tool):
    # Run a small sh script, wait for its completion and return its output to stdout as a string.
    # Do not use this for "big" scripts with a lot of output.

    EXECUTABLE = 'sh'  # dynamic helper, looked-up in the context

    ENCODING = 'utf-8'

    NAME = 'scriptlet'
    SCRIPTLET = ''  # this will be executed by sh - overwrite in subclass

    output = dlb.ex.Tool.Output.Object(explicit=False)

    def get_scriptlet_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return []

    async def redo(self, result, context):
        script = '\n'.join(textwrap.dedent(self.SCRIPTLET).strip().splitlines())
        _, stdout, _ = \
            await context.execute_helper(
                self.EXECUTABLE,
                ['-c', '-', script, self.NAME] + [c for c in self.get_scriptlet_arguments()],
                stdout=subprocess.PIPE)
        result.output = stdout.decode(self.ENCODING)
