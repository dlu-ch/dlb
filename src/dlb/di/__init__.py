# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Write formatted and indented lines to represent hierarchic diagnostic information to a file.
This module uses levels compatible with the ones of the 'logging' module."""

__all__ = [
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL',
    'format_time_ns',
    'set_threshold_level',
    'is_unsuppressed_level',
    'get_level_indicator',
    'set_output_file',
    'format_message',
    'Cluster',
    'inform'
]

import sys
import math
import re
import time
from typing import Dict, List, Optional, Sequence, Tuple

from .. import ut


# these correspond to logging.* but are fixed (see https://docs.python.org/3/library/logging.html#logging-levels)
# not importing 'logging' reduced import time for this module
DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50


_RESERVED_TITLEEND_CHARACTERS = " .]\b"
_RESERVED_TITLESTART_CHARACTERS = "'|" + _RESERVED_TITLEEND_CHARACTERS

_FIELD_SEPARATORS = frozenset('\t\b')
_FIELD_SEPARATOR_REGEX = re.compile(r'([\t\b])')

_output_file = sys.stderr

_clusters = []

_lowest_unsuppressed_level: int = 1 if sys.flags.verbose else INFO

# time.monotonic_ns() of the first output message with enabled timing information
_first_monotonic_ns: Optional[int] = None


def _get_time_resolution():
    dt = time.get_clock_info('monotonic').resolution
    n = math.ceil(-math.log10(dt)) + 1
    return max(1, min(6, n))


# number of decimal places of relative time in seconds
_decimal_places_for_time: int = _get_time_resolution()
del _get_time_resolution


def format_time_ns(time_ns: int) -> str:
    return ut.format_time_ns(time_ns, _decimal_places_for_time)


# these correspond to the first characters of the standard logging.getLevelName[...]
# the level names of 'logging' are meant to be changed by the user, so do not rely on them:
_level_indicator_by_level = {
    DEBUG: 'D',
    INFO: 'I',
    WARNING: 'W',
    ERROR: 'E',
    CRITICAL: 'C'
}


def _unindent_and_normalize_message_lines(message, *, name: str) -> Tuple[List[str], bool]:
    # Return the unindented lines of *message*.
    # Use *name* as the argument name for exception messages.
    #
    # Properties of *lines*:
    #
    #   - at least 1 line
    #   - first line is not empty
    #   - last line is not empty
    #   - 2 successive lines are not both empty
    #   - no line ends with a space character
    #   - first line does not start with character in _RESERVED_LINESTART_CHARACTERS
    #   - every line except the first starts with '|'

    continuation_indentation = '  '

    lines = []
    first_indentation = None  # leading white-space of first non-empty line
    has_field_separator = False
    last_was_empty = None

    for lineno0, line in enumerate(message.splitlines()):
        line = line.rstrip()  # keeps '\b'

        if not line:
            if last_was_empty is False:  # not first line and last line was not empty
                lines.append('|')
                last_was_empty = True
            continue

        last_was_empty = False
        characters = set(line)
        characters_without_field_seps = characters - _FIELD_SEPARATORS
        c = min(characters_without_field_seps or ' ')
        if c < ' ':
            raise ValueError(
                f"{name!r} must not contain ASCII control characters except '\\t' and '\\b', "
                f"unlike {c!r} in line {lineno0 + 1}"
            )
        has_field_separator = has_field_separator or characters_without_field_seps != characters

        if not lines:
            # is first non-empty line
            stripped_line = line.lstrip()  # keeps '\b'
            first_indentation = line[:len(line) - len(stripped_line)]

            line = stripped_line
            if line[0] in _RESERVED_TITLESTART_CHARACTERS:
                raise ValueError(f"first non-empty line in {name!r} must not start with character {line[0]!r}")
            if line[-1] in _RESERVED_TITLEEND_CHARACTERS:
                raise ValueError(f"first non-empty line in {name!r} must not end with {line[-1]!r}")
        else:
            line = line[len(first_indentation):] if line[:len(first_indentation)] == first_indentation else ''
            if not line.startswith(continuation_indentation):
                raise ValueError(
                    f"each continuation line in {name!r} must be indented at "
                    f"least {len(continuation_indentation)} spaces more than the first non-empty line, "
                    f"unlike line {lineno0 + 1}"
                )
            line = '| ' + line[len(continuation_indentation):]

        lines.append(line)

    if last_was_empty is True:
        del lines[-1]

    if not lines:
        raise ValueError(f"{name!r} must contain at least one non-empty line")

    return lines, has_field_separator


def _expand_fields(lines: Sequence[str]) -> List[str]:

    fields_per_line: List[List[str]] = []
    len_by_field_index: Dict[int, int] = {}

    for line in lines:
        r = _FIELD_SEPARATOR_REGEX.split(line)  # length of list is uneven
        if len(r) > 1:
            fields = [r[i] + r[i + 1] for i in range(0, len(r) - 1, 2)] + [r[-1]]
        else:
            fields = [r[0]]

        fields_per_line.append(fields)
        for i, field in enumerate(fields):
            if field and field[-1] in '\t\b':
                len_by_field_index[i] = max(len(field) - 1, len_by_field_index.get(i, 0))

    # len_by_field_index[i] is the length after justification of field[i] that ends in '\t' or '\b'

    expanded_lines = []
    for line_index, fields in enumerate(fields_per_line):
        line = ''

        # '\t' -> left align, '\b' -> right align
        for field_index, field in enumerate(fields):
            if field and field[-1] in '\t\b':
                justifier = str.rjust if field[-1] == '\b' else str.ljust
                field = justifier(field[:-1], len_by_field_index[field_index])
            line = line + field

        expanded_lines.append(line.rstrip())

    return expanded_lines


def _format_message(message, *data, name: str, prefix: str) -> str:
    # must be fast for single line

    if not isinstance(message, str):
        raise TypeError(f"{name!r} must be a str")

    lines, has_field_separator = _unindent_and_normalize_message_lines(message, name=name)
    if has_field_separator:
        lines = _expand_fields(lines)  # assuming len(*prefix*) = 2

    lines[0] = prefix + lines[0]

    last_was_empty = None
    for d in data:
        text = d if isinstance(d, str) else repr(d)
        data_lines = text.splitlines() or ['']  # at least one line per *d*
        for data_line in data_lines:
            if data_line and min(data_line) < ' ':
                data_line = ''.join(c if c >= ' ' else ' ' for c in data_line)
            data_line = data_line.rstrip()
            if data_line:
                lines.append('| ' + data_line)
                last_was_empty = False
            elif not last_was_empty:
                lines.append('|')
                last_was_empty = True
    if last_was_empty is True:
        del lines[-1]

    if len(lines) == 1:
        return lines[0]

    # - each line consists only of characters >= U+0020
    # - no line ends with 2 space characters
    # - last line does not end with a space character
    # - each line except the last one ends with 1 space character
    # - successive lines are separated by '\n'
    # - the "positions" of the (removed) '\t', '\b' are aligned over all lines

    return ' \n  '.join(lines)


def _checked_level(level):
    try:
        level = int(level)
    except (TypeError, ValueError):
        raise TypeError("'level' must be something convertible to an int")

    if not level > 0:
        raise ValueError(f"'level' must be positive")

    return level


def set_threshold_level(level):
    global _lowest_unsuppressed_level
    _lowest_unsuppressed_level = _checked_level(level)


def is_unsuppressed_level(level):
    return _checked_level(level) >= _lowest_unsuppressed_level


def get_level_indicator(level: int) -> str:
    level = _checked_level(level)
    standard_level = max([DEBUG] + [s for s in _level_indicator_by_level if s <= level])
    return _level_indicator_by_level[standard_level][0]


def set_output_file(file):
    if not hasattr(file, 'write'):
        raise TypeError(f"'file' does not have a 'write' method: {file!r}")

    global _output_file
    _output_file, f = file, _output_file
    return f


def format_message(message: str, *data, level: int) -> str:  # idempotent only for single lines
    return _format_message(message, *data, name='message', prefix=get_level_indicator(level) + ' ')


def _indent_message(message: str, nesting: int):
    indentation = '  ' * max(nesting, 0)
    return '\n'.join(indentation + line for line in message.splitlines())


def _append_to_title_of_formatted(formatted_message: str, suffix: str) -> str:
    initial_line, lf, rest = formatted_message.partition('\n')
    if not lf:
        return initial_line + suffix  # single line
    return initial_line[:-1] + suffix + initial_line[-1] + lf + rest


def _get_relative_monotonic_ns(monotonic_ns):
    global _first_monotonic_ns
    if _first_monotonic_ns is None:
        _first_monotonic_ns = monotonic_ns
    return max(0, monotonic_ns - _first_monotonic_ns)


def _get_relative_time_suffix(monotonic_ns: Optional[int]):
    if monotonic_ns is None:
        return ''

    return " [+{}s]".format(format_time_ns(_get_relative_monotonic_ns(monotonic_ns)))


class Cluster:
    def __init__(self, message: str, *, level: int = INFO, is_progress: bool = False,
                 with_time: bool = False):
        # must be fast
        self._level: int = _checked_level(level)
        self._pre_formatted_title = _format_message(message, name='message', prefix='_ ')  # use '_' for level indicator
        self._is_progress = bool(is_progress)
        self._with_time: bool = bool(with_time)
        self._monotonic_ns: Optional[int] = None
        self._did_inform: bool = False
        self._nesting_level: Optional[int] = None  # set in __enter__()

    def inform_title(self):
        if not self._did_inform:
            for c in _clusters:
                if c == self:
                    break
                c.inform_title()  # is parent of self

            title = get_level_indicator(self._level) + self._pre_formatted_title[1:]
            suffix = '...' if self._is_progress else ''
            suffix += _get_relative_time_suffix(self._monotonic_ns)
            if suffix:
                title = _append_to_title_of_formatted(title, suffix)

            indented_title = _indent_message(title, self._nesting_level)
            _output_file.write(indented_title + '\n')
            self._did_inform = True

    def __enter__(self) -> None:
        self._nesting_level = len(_clusters)
        if self._with_time:
            self._monotonic_ns = time.monotonic_ns()
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
                result = '{l} done.'.format(l=get_level_indicator(min(self._level, INFO)))
            else:
                result = '{l} failed with {e}.'.format(
                    l=get_level_indicator(max(self._level, ERROR)),
                    e=exc_val.__class__.__qualname__)

            if self._monotonic_ns is not None:
                suffix = _get_relative_time_suffix(time.monotonic_ns())
                result = _append_to_title_of_formatted(result, suffix)

            indented_result = _indent_message(result, nesting + 1)
            _output_file.write(indented_result + '\n')


def inform(message, *data, level: int = INFO, with_time: bool = False) -> bool:
    level = _checked_level(level)

    formatted_message = format_message(message, *data, level=level)

    if not is_unsuppressed_level(level):
        return False

    if with_time:
        suffix = _get_relative_time_suffix(time.monotonic_ns())
        formatted_message = _append_to_title_of_formatted(formatted_message, suffix)

    if _clusters:
        _clusters[-1].inform_title()

    _output_file.write(_indent_message(formatted_message, len(_clusters)) + '\n')
    return True
