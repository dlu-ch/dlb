# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Adjust how uncaught exceptions are reported."""

# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.exctrace
#
#   dlb_contrib.exctrace.enable_compact_with_cwd(traceback_file='build/out/traceback.log')
#
#   ...

__all__ = ['enable_compact_with_cwd']

from typing import Optional
import dlb.fs


def _output_compact_tb(etype, value, tb,
                       current_directory_path_abs: str,
                       traceback_file_path_abs: Optional[str],
                       involved_line_limit: int):
    import traceback
    import os.path
    import dlb.di

    involved_line_limit = max(0, involved_line_limit)

    if traceback_file_path_abs is not None:
        os.makedirs(os.path.dirname(traceback_file_path_abs), exist_ok=True)
        with open(traceback_file_path_abs, 'w') as f:
            traceback.print_exception(etype, value, tb, file=f)

    involved_lines = []
    if involved_line_limit > 0 and current_directory_path_abs is not None:
        for frame_summary in traceback.extract_tb(tb):
            p = frame_summary.filename
            if os.path.isabs(p):
                p = os.path.realpath(p)
                if os.path.isfile(p) and p.startswith(current_directory_path_abs):
                    p = p[len(current_directory_path_abs):]
                    involved_lines.append((p, frame_summary.lineno))

    formatted_exceptions = [repr(e.strip()) for e in traceback.format_exception_only(etype, value)]
    msg = 'aborted by exception:' + '\n    '.join([''] + formatted_exceptions)
    if traceback_file_path_abs is not None:
        msg += f'\n    traceback: {traceback_file_path_abs!r}'

    with dlb.di.Cluster(msg, level=dlb.di.CRITICAL):
        if involved_lines:
            formatted_lines = [f'{path!r}:{lineno}' for path, lineno in involved_lines]
            if len(involved_lines) > involved_line_limit:
                formatted_lines = formatted_lines[:involved_line_limit]
            formatted_lines[-1] = f'{formatted_lines[-1]} (nearest to cause)'
            if len(involved_lines) > involved_line_limit:
                formatted_lines.append('...')
            dlb.di.inform(
                f'involved lines from files in {current_directory_path_abs!r}:' +
                '\n    '.join([''] + formatted_lines))


def enable_compact_with_cwd(*, traceback_file: Optional[dlb.fs.PathLike] = None,
                            involved_line_limit: int = 5):
    # Enable the compact and structured output of uncaught exceptions to dlb.di with level dlb.di.CRITICAL and
    # optionally the output of the full backtrace to a file.
    #
    # This (only) replaces sys.excepthook.
    # Restoring sys.excepthook restores the previous behaviour.
    #
    # If involved_line_limit > 0:
    # The current working directory of the calling process is considered the root directory of (Python) files of
    # primary interest. If later the exception traceback contains an existing regular file whose os.path.realpath() has
    # this directory as a prefix, it is considered a file of interest.
    # The lines in files of interest are output with level dlb.di.INFO. If the number of such lines is greater than
    # *involved_line_limit*, only the *involved_line_limit* lines nearest to the top of the call stack are output,
    # followed by '...'.
    #
    # If *traceback_file* is not None:
    # The complete traceback is written to *traceback_file*. All parent directory are created if the do not exist.
    # The file ist overwritten if it exits.
    #
    # Example output after enable_compact_with_cwd(traceback_file='build/out/traceback.log'', involved_line_limit=3)
    #
    #   C aborted by exception:
    #     | "dlb.ex.HelperExecutionError: execution of 'gcc' returned unexpected exit code 1"
    #     | traceback: '../build/out/traceback.log'
    #     I involved lines from files in '.../':
    #       | 'build.py':112
    #       | 'build.py':87
    #       | 'build.py':50 (nearest to cause)
    #       | ...

    import sys
    import os.path

    current_directory_path_abs = os.path.join(os.path.realpath(os.getcwd()), '')

    traceback_file_path_abs = None
    if traceback_file is not None:
        traceback_file_path_abs = os.path.realpath(dlb.fs.Path(traceback_file).native)

    if not isinstance(involved_line_limit, int):
        raise TypeError("'involved_line_limit' must be an int")

    def excepthook(etype, value, tb):
        return _output_compact_tb(
            etype, value, tb,
            current_directory_path_abs,
            traceback_file_path_abs,
            involved_line_limit)

    sys.excepthook = excepthook
