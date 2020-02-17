# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Output formatted indented printable ASCII lines to represent hierarchic diagnostic information.
It uses the level mechanism of the 'logging' module.
The filtering and destination is determined by the active context.
"""

__all__ = ('Cluster', 'inform')

import re
import typing
import logging


_RESERVED_LINESTART_CHARACTERS = " |'"

_clusters = []

min_unsuppressed_level: int = 1


def _first_non_printable_character_in(s: str, keep: str = '') -> typing.Optional[str]:
    for c in s:
        if not (0x20 <= ord(c) < 0xFF) and c not in keep:
            return c


def _format_messages(*, _prefix='', _suffix='', **messages: str) -> typing.List[str]:
    formatted_messages = []

    for message_name, message in messages.items():

        if not isinstance(message, str):
            raise TypeError(f"{message_name!r} must be a str")

        lines = str(message).splitlines()
        continuation_line_prefix = '  | '

        normalized_lines = []
        indentation_of_first_line = 0

        for lineno0, line in enumerate(lines):
            c = _first_non_printable_character_in(line, '\t\b')
            if c is not None:
                msg = (
                    f"{message_name!r} must only contain printable ASCII characters except '\\t' and '\\b', "
                    f"unlike {c!r} in line {lineno0 + 1}"
                )
                raise ValueError(msg)
            line = line.rstrip()
            if line:
                stripped_line = line.lstrip()  # not empty
                indentation = len(line) - len(stripped_line)
                if not normalized_lines:
                    # is first non empty line
                    indentation_of_first_line = indentation
                    if stripped_line[0] in _RESERVED_LINESTART_CHARACTERS:
                        msg = (
                            f"first non-empty line in {message_name!r} must not start with "
                            f"reserved character {stripped_line[0]!r}"
                        )
                        raise ValueError(msg)
                    if stripped_line[-1] == '.':
                        msg = f"first non-empty line in {message_name!r} must not end with '.'"
                        raise ValueError(msg)
                    line = _prefix + stripped_line + _suffix
                elif line:
                    if indentation < indentation_of_first_line + len(continuation_line_prefix):
                        msg = (
                            f"each continuation line in {message_name!r} must be indented at "
                            f"least {len(continuation_line_prefix)} spaces more than the first non-empty line, "
                            f"unlike line {lineno0 + 1}"
                        )
                        raise ValueError(msg)
                    line = line[indentation_of_first_line:]
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
                line = continuation_line_prefix + line[len(continuation_line_prefix):]
            if line_index + 1 < len(normalized_lines):
                line = line + ' '  # not last line

            formatted_lines.append(line)

        # - each line consists only of printable ASCII characters
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


def get_level_marker(level: int) -> str:
    level = _checked_level(level)

    standard_levels = (
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL
    )

    standard_level = max([logging.DEBUG] + [l for i, l in enumerate(standard_levels) if l <= level])
    return logging.getLevelName(standard_level)[0]


def format_message(message: str, level: int) -> str:  # idempotent only for single lines
    return _format_messages(_prefix=get_level_marker(level) + ' ', message=message)[0]


def _indent_message(message: str, nesting: int):
    indentation = '  ' * max(nesting - 1, 0)
    return '\n'.join(indentation + line for line in message.splitlines())


class Cluster:
    def __init__(self, title: str = '', *, level: int = logging.INFO, is_progress: bool = False):
        self._level = _checked_level(level)
        self._is_progress = bool(is_progress)
        suffix = '...' if self._is_progress else ''
        self._formatted_title = _format_messages(_prefix=get_level_marker(level) + ' ', _suffix=suffix, title=title)[0]
        self._did_inform = False

    def inform_title(self):
        if not self._did_inform:
            for c in _clusters:
                c.inform_title()
            indented_title = _indent_message(self._formatted_title, len(_clusters))
            print(indented_title)
            self._did_inform = True

    def __enter__(self) -> None:
        if self._level >= min_unsuppressed_level:
            self.inform_title()
        _clusters.append(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._did_inform and self._is_progress:
            summary = f"failed with {exc_val.__class__.__qualname__}." if exc_val is not None else 'done.'
            summary = get_level_marker(min(self._level, logging.INFO)) + ' ' + summary
            indented_summary = _indent_message(summary, len(_clusters) + 1)
            print(indented_summary)
        if _clusters[-1] == self:
            del _clusters[-1]


def inform(message, *, level: int = logging.INFO) -> bool:
    level = _checked_level(level)
    indented_message = _indent_message(format_message(message, level=level), len(_clusters) + 1)

    if level < min_unsuppressed_level:
        return False

    if not _clusters:
        print(message)
        return True

    _clusters[-1].inform_title()
    print(indented_message)
