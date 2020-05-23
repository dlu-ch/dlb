# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Query environment variables after the execution of a Microsoft batch file."""

# cmd: <https://docs.microsoft.com/en-us/windows-server/administration/windows-commands/cmd>
# Executable: 'cmd.exe'
#
# The batch file is executed with the working tree's root as its working directory.
# Its only command-line argument (%1) is the relative path of an empty temporary directory (consisting of exactly
# 3 components of only lower-case ASCII letters, decimal digits and '.') to be used by the batch file.
#
# The entire environment is exposed to the batch file.
# A redo is performed at every run.
#
# Note:
# It is *not* possible to reliably output the value of an environment variable with cmd.exe alone if it can contain
# a line separator (an inefficient and complicated method for a single variable is given in the comment below)
# - hard to believe but true.
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.msbatch
#
#   # content of 'setup.bat':
#   #   @call ...
#   #   @if %errorlevel% neq 0 exit
#   #   @cd %1
#   #   @python3 -m dlb_contrib.exportenv
#
#   with dlb.ex.Context():
#       ... = dlb_contrib.msbatch.RunEnvBatch(batch_file='setup.bat') \
#                 .exported_environment['LIB']

__all__ = ['RunEnvBatch']

import sys
import os.path

import dlb.fs
import dlb.ex
import dlb_contrib.exportenv

assert sys.version_info >= (3, 7)


class BatchFilePath(dlb.fs.WindowsPath):
    def check_restriction_to_base(self, components_checked: bool):
        if not self.is_dir() and self.parts:
            _, ext = os.path.splitext(self.parts[-1])
            if not (ext.lower().endswith('.bat')):
                raise ValueError("must end with '.bat'")


class RunEnvBatch(dlb.ex.Tool):
    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'cmd.exe'

    batch_file = dlb.ex.input.RegularFile(cls=BatchFilePath)
    exported_environment = dlb.ex.output.Object(explicit=False)

    async def redo(self, result, context):
        batch_file = result.batch_file
        if not batch_file.is_absolute():
            batch_file = context.root_path / batch_file

        with context.temporary(is_dir=True) as tmp_dir:
            # Note:
            # - cmd.exe does *not* follow the quoting rules of the MS C runtime - it cannot handle \" and \\
            # - Python (in submodule.Popen) assumes it does
            # - Therefore, *command* must be a single token and (arbitrary) paths can only be propagated in
            #   environment variables
            # - These all call a^b.bat (when run from cmd):
            #     cmd /s /c "a^^b.bat"
            #     cmd /s /c a^^^^b.bat

            quoted_batch_file_path = str(batch_file.native).replace('^', '^^')

            # Note:
            # - cmd.exe must not be started with '/u' or Python cannot decode stdout, stderr
            # - do not use temporary directory as working directory because batch files that keep files open are common
            await context.execute_helper(
                self.EXECUTABLE,
                ['/s', '/c', quoted_batch_file_path, context.working_tree_path_of(tmp_dir, allow_temporary=True)],
                forced_env=os.environ)

            envvar_file = tmp_dir / dlb_contrib.exportenv.FILE_NAME
            try:
                exported_environment = dlb_contrib.exportenv.read_exported(envvar_file.native)
            except FileNotFoundError:
                msg = (
                    f"exported environment file not found: {dlb_contrib.exportenv.FILE_NAME!r}\n"
                    f"  | create it in the batch file with 'python3 -m dlb_contrib.exportenv'"
                )
                raise RuntimeError(msg) from None
            result.exported_environment = exported_environment

        return True


# To query an environment variable 'v' that may contain a line separator:
#
#   cmd.exe /e:on /u /c set v^&set v=^&set v>t
#
# If an environment variable 'v' exists and does not contain a line separator, this sets %errorlevel% to 0 and creates
# an UTF-16LE encoded textfile that starts with 'v=', followed by an even number of lines where the first half and the
# second half are equal.
# If no environment variable 'v' exists, it sets %errorlevel% to 1.
