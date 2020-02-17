# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Write formatted and indented lines to represent hierarchic diagnostic information to a file.
This module uses levels of the 'logging' module.
"""

__all__ = ()

import sys
import re
import time
import textwrap
import typing
import logging


_RESERVED_TITLEEND_CHARACTERS = " .]"
_RESERVED_TITLESTART_CHARACTERS = "'|" + _RESERVED_TITLEEND_CHARACTERS

_CONTINUATION_LINE_PREFIX = '  | '
_CONTINUATION_INDENTATION = ' ' * len(_CONTINUATION_LINE_PREFIX)

_output_file = sys.stderr

_clusters = []

_lowest_unsuppressed_level: int = logging.INFO

# time.time_ns() of the first output message with enabled timing information
_first_time_ns: typing.Optional[int] = None


# these correspond to the first characters of the standard logging.getLevelName[...]
# the level names of 'logging' are meant to be changed by the user, so do not rely on them:
_level_indicator_by_level = {
    logging.DEBUG: 'D',
    logging.INFO: 'I',
    logging.WARNING: 'W',
    logging.ERROR: 'E',
    logging.CRITICAL: 'C'
}


def _first_control_character_in(s: str, keep: str = '') -> typing.Optional[str]:
    for c in s:
        if ord(c) < 0x20 and c not in keep:
            return c


def _format_messages(*, _prefix='', **messages: str) -> typing.List[str]:
    formatted_messages = []

    for message_name, message in messages.items():
        if not isinstance(message, str):
            raise TypeError(f"{message_name!r} must be a str")

        lines = str(textwrap.dedent(message)).splitlines()

        normalized_lines = []
        for lineno0, line in enumerate(lines):
            c = _first_control_character_in(line, '\t\b')
            if c is not None:
                msg = (
                    f"{message_name!r} must not contain ASCII control characters except '\\t' and '\\b', "
                    f"unlike {c!r} in line {lineno0 + 1}"
                )
                raise ValueError(msg)
            line = line.rstrip()
            if line:
                if not normalized_lines:
                    # is first non empty line
                    if line[0] in _RESERVED_TITLESTART_CHARACTERS:
                        msg = (
                            f"first non-empty line in {message_name!r} must not start with "
                            f"reserved character {line[0]!r}"
                        )
                        raise ValueError(msg)
                    if line[-1] in _RESERVED_TITLEEND_CHARACTERS:
                        msg = f"first non-empty line in {message_name!r} must not end with {line[-1]!r}"
                        raise ValueError(msg)
                    line = _prefix + line
                elif line:
                    if not line.startswith(_CONTINUATION_INDENTATION):
                        msg = (
                            f"each continuation line in {message_name!r} must be indented at "
                            f"least {len(_CONTINUATION_LINE_PREFIX)} spaces more than the first non-empty line, "
                            f"unlike line {lineno0 + 1}"
                        )
                        raise ValueError(msg)
                if line or (normalized_lines and normalized_lines[-1] != ''):
                    normalized_lines.append(line)

        if not normalized_lines:
            raise ValueError(f"{message_name!r} must contain at least one non-empty line")

        # properties of normalized_lines:
        # - at least 1 line
        # - first line is not empty
        # - last line is not empty
        # - 2 successive lines are not empty
        # - no line ends with a space character
        # - first line does not start with character in _RESERVED_LINESTART_CHARACTERS
        # - every non-empty line except the first starts with 2 space character followed by a non-space character

        fields_per_line: typing.List[typing.List[str]] = []
        len_by_field_index: typing.Dict[int, int] = dict()

        for line in normalized_lines:
            r = re.split(r'([\t\b])', line)  # length of list is uneven
            if len(r) > 1:
                fields = [r[i] + r[i + 1] for i in range(0, len(r) - 1, 2)] + [r[-1]]
            else:
                fields = [r[0]]

            assert line == ''.join(fields)
            fields_per_line.append(fields)
            for i, field in enumerate(fields):
                if field and field[-1] in '\t\b':
                    len_by_field_index[i] = max(len(field) - 1, len_by_field_index.get(i, 0))

        # len_by_field_index[i] is the length after justification of field[i] that ends in '\t' or '\b'

        formatted_lines = []
        for line_index, fields in enumerate(fields_per_line):
            line = ''

            # '\t' -> left align, '\b' -> right align
            for field_index, field in enumerate(fields):
                if field and field[-1] in '\t\b':
                    justifier = str.rjust if field[-1] == '\b' else str.ljust
                    field = justifier(field[:-1], len_by_field_index[field_index])
                line = line + field

            if formatted_lines:
                line = _CONTINUATION_LINE_PREFIX + line[len(_CONTINUATION_LINE_PREFIX):]
            if line_index + 1 < len(normalized_lines):
                line = line + ' '  # not last line

            formatted_lines.append(line)

        # - each line consists only of characters >= U+0020
        # - no line ends with 2 space characters
        # - last line does not end with a space character
        # - each line except the last one ends with 1 space character
        # - successive lines are separated by '\n'
        # - the "positions" of the (removed) '\t', '\b' are aligned over all lines

        formatted_messages.append('\n'.join(formatted_lines))

    return formatted_messages


def _checked_level(level):
    try:
        level = int(level)
    except (TypeError, ValueError):
        raise TypeError("'level' must be something convertible to an int")

    if level <= logging.NOTSET:
        raise ValueError(f"'level' must be > {logging.NOTSET}")

    return level


def set_threshold_level(level):
    global _lowest_unsuppressed_level
    _lowest_unsuppressed_level = _checked_level(level)


def is_unsuppressed_level(level):
    return _checked_level(level) >= _lowest_unsuppressed_level


def get_level_indicator(level: int) -> str:
    level = _checked_level(level)
    standard_level = max([logging.DEBUG] + [s for s in _level_indicator_by_level if s <= level])
    return _level_indicator_by_level[standard_level][0]


def set_output_file(file):
    if not hasattr(file, 'write'):
        raise TypeError(f"'file' does not have a 'write' method: {file!r}")

    global _output_file
    _output_file, f = file, _output_file
    return f


def format_message(message: str, level: int) -> str:  # idempotent only for single lines
    return _format_messages(_prefix=get_level_indicator(level) + ' ', message=message)[0]


def _indent_message(message: str, nesting: int):
    indentation = '  ' * max(nesting, 0)
    return '\n'.join(indentation + line for line in message.splitlines())


def _append_to_title_of_formatted(formatted_message: str, suffix: str) -> str:
    initial_line, lf, rest = formatted_message.partition('\n')
    if not lf:
        return initial_line + suffix  # single line
    return initial_line[:-1] + suffix + initial_line[-1] + lf + rest


def _get_relative_time_ns(time_ns):
    global _first_time_ns
    if _first_time_ns is None:
        _first_time_ns = time_ns
    return max(0, time_ns - _first_time_ns)


def _get_relative_time_suffix(time_ns: typing.Optional[int]):
    if time_ns is None:
        return ''
    return ' [+{:.6f}s]'.format(_get_relative_time_ns(time_ns) / 1e9)


class Cluster:
    def __init__(self, message: str, *, level: int = logging.INFO, is_progress: bool = False,
                 with_time: bool = False):
        self._level: int = _checked_level(level)
        self._formatted_title = _format_messages(_prefix=get_level_indicator(level) + ' ', title=message)[0]
        self._is_progress = bool(is_progress)
        self._with_time: bool = bool(with_time)
        self._time_ns: typing.Optional[int] = None
        self._did_inform: bool = False
        self._nesting_level: typing.Optional[int] = None  # set in __enter__()

    def inform_title(self):
        if not self._did_inform:
            for c in _clusters:
                if c == self:
                    break
                c.inform_title()  # is parent of self

            title = self._formatted_title
            suffix = '...' if self._is_progress else ''
            suffix += _get_relative_time_suffix(self._time_ns)
            if suffix:
                title = _append_to_title_of_formatted(title, suffix)

            indented_title = _indent_message(title, self._nesting_level)
            _output_file.write(indented_title + '\n')
            self._did_inform = True

    def __enter__(self) -> None:
        self._nesting_level = len(_clusters)
        if self._with_time:
            self._time_ns = time.time_ns()
        if is_unsuppressed_level(self._level):
            self.inform_title()
        _clusters.append(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        nesting = self._nesting_level

        self._nesting_level = None
        if _clusters[-1] == self:
            del _clusters[-1]

        if self._did_inform and self._is_progress:
            if exc_val is None:
                result = '{l} done.'.format(l=get_level_indicator(min(self._level, logging.INFO)))
            else:
                result = '{l} failed with {e}.'.format(
                    l=get_level_indicator(max(self._level, logging.ERROR)),
                    e=exc_val.__class__.__qualname__)

            if self._time_ns is not None:
                suffix = _get_relative_time_suffix(self._time_ns)
                result = _append_to_title_of_formatted(result, suffix)

            indented_result = _indent_message(result, nesting + 1)
            _output_file.write(indented_result + '\n')


def inform(message, *, level: int = logging.INFO, with_time: bool = False) -> bool:
    level = _checked_level(level)

    indented_message = _indent_message(format_message(message, level=level), len(_clusters))
    if with_time:
        suffix = _get_relative_time_suffix(time.time_ns())
        indented_message = _append_to_title_of_formatted(indented_message, suffix)

    if not is_unsuppressed_level(level):
        return False

    if _clusters:
        _clusters[-1].inform_title()

    _output_file.write(indented_message + '\n')
    return True
