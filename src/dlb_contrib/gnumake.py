# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Parse GNU Make rules."""

# GNU Make: <https://www.gnu.org/software/make/>
# Make: <https://pubs.opengroup.org/onlinepubs/009695399/utilities/make.html>
# Tested with: GNU Make 4.2.1
#
# Usage example:
#
#   import sys
#   import dlb.fs
#   import dlb_contrib.gnumake
#
#   makefile = dlb.fs.Path(...)
#
#   sources = set()
#   with open(makefile.native, 'r', encoding=sys.getfilesystemencoding()) as f:
#       for r in dlb_contrib.gnumake.sources_from_rules(f):
#           sources |= set(r)

__all__ = ['sources_from_rules', 'additional_sources_from_rule']

import sys
import string
from typing import Iterable, List

assert sys.version_info >= (3, 7)


_WHITESPACE_EXCEPT_HT = string.whitespace.replace('\t', '')
_WILDCARD = '*?[]'


def _first_position_of(s: str, characters_to_find: str, start: int = 0) -> int:
    indices = tuple(s.find(c, start) for c in characters_to_find)
    try:
        return min(i for i in indices if i >= 0)
    except ValueError:  # if empty
        return -1


def sources_from_rules(lines: Iterable[str]) -> List[List[str]]:
    # Extract source paths from Make rules in *lines* and return a list of source path for each rule in *lines*.
    # Line separators at the end of the lines in *lines* are removed.
    #
    # Escape the following characters with a preceding '\\':
    # '#', ':', ';', '*', '?', '[', ']', whitespace (except line separators)
    # Escape the following characters with a preceding '$': '$'.
    # Lines can be continued with a singled trailing '\\'.
    #
    # This parser is meant for Makefiles as understood by GNU Make 4.0. Since escaping and quoting of characters
    # is severely underspecified for Makefiles, portability issues are to be expected with other implementations of
    # Make if paths contain "special characters".
    #
    # Limitations of possible paths by GNU Make:
    #
    #   - path must not contain a line separators
    #   - path nost not contain '\\' followed by a escapable character
    #
    # All lines in *lines* must be of one of the following types:
    #
    #   - empty
    #   - whitespace and comment only
    #   - rule (e.g. 'a.o: a.c')
    #   - recipe (e.g. '\t$(CC) -c -o $@ $< $(CFLAGS)')
    #
    # Unsupported (raise ValueError):
    #
    #   - multiple '\\' at the end of a line
    #   - pattern rules (e.g. '%.o: %.c')
    #   - double-colon rules (e.g. 'a.o:: a.c')

    # see eval() in read.c of https://ftp.gnu.org/gnu/make/make-4.0.tar.gz

    # note: gcc 8.3.0 erroneously does not quote ':' and ';' in filename with -M

    rule_sources = []

    whitespace_separated_rule_tokens = []

    to_be_continued = False  # is a line expected to follow?
    continued_ended_with_comment = False  # is a line expected to follow that is a comment?

    for lineno0, unprocessed_line in enumerate(lines):
        unprocessed_line = unprocessed_line.rstrip('\n\r')

        if unprocessed_line[-2:] == '\\\\':
            # GNU Make handles multiple backslashes at the end of the line in an efficient but strange way that makes
            # correct escaping impossible. Do not allow this since this probably differs between Make implementation.
            # See readline() in read.c and collapse_continuations() in misc.c
            raise ValueError(f"multiple '\\' at end of line {lineno0 + 1}")

        # https://www.gnu.org/software/make/manual/html_node/Splitting-Lines.html
        # https://www.gnu.org/software/make/manual/html_node/Splitting-Recipe-Lines.html#Splitting-Recipe-Lines

        # replace escaped characters, ignore comments in line and split into tokens at whitespace
        first_unprocessed_in_line = 0
        unprocessed_line = unprocessed_line.lstrip(string.whitespace if to_be_continued else _WHITESPACE_EXCEPT_HT)

        to_be_continued = False
        while True:
            if unprocessed_line[-1:] == '\\':  # even in comment!
                # combine with next line and treat as ' '
                unprocessed_line = '' if continued_ended_with_comment else unprocessed_line[:-1]
                to_be_continued = True
            elif continued_ended_with_comment:
                unprocessed_line = ''
                continued_ended_with_comment = False

            if unprocessed_line[:1] == '\t':  # cmd_prefix
                unprocessed_line = ''

            i = _first_position_of(unprocessed_line,
                                   '\\#$:;' + _WILDCARD + string.whitespace,
                                   first_unprocessed_in_line)
            if i < 0:
                break
            if unprocessed_line[i] == '#':
                unprocessed_line = unprocessed_line[:i]
                continued_ended_with_comment = to_be_continued
                break
            if unprocessed_line[i] == '\\':
                # https://www.gnu.org/software/make/manual/make.html#Wildcards
                if i + 1 < len(unprocessed_line) and unprocessed_line[i + 1] in '#:;' + _WILDCARD + string.whitespace:
                    unprocessed_line = unprocessed_line[:i] + unprocessed_line[i + 1:]  # remove '\\'
                # '$' and '\\' cannot be quoted by '\\'
                # assume that is not part of a pattern rule, so '%' cannot be quoted by '\\'
                first_unprocessed_in_line = i + 1
            elif unprocessed_line[i] == '$':
                if not (i + 1 < len(unprocessed_line) and unprocessed_line[i + 1] == '$'):
                    raise ValueError(f"unquoted '$' in line {lineno0 + 1}")
                unprocessed_line = unprocessed_line[:i] + unprocessed_line[i + 1:]
                first_unprocessed_in_line = i + 1
            elif unprocessed_line[i] in ':;':
                if i > 0:
                    whitespace_separated_rule_tokens.append(unprocessed_line[:i])
                whitespace_separated_rule_tokens.append(unprocessed_line[i])
                unprocessed_line = unprocessed_line[i + 1:]
            elif unprocessed_line[i] in _WILDCARD:
                raise ValueError(f"unquoted wildcard character in line {lineno0 + 1}")
            else:  # unescaped whitespace
                if i > 0:
                    whitespace_separated_rule_tokens.append(unprocessed_line[:i])
                unprocessed_line = unprocessed_line[i + 1:].lstrip(string.whitespace)

        if unprocessed_line:
            whitespace_separated_rule_tokens.append(unprocessed_line)

        if not to_be_continued and whitespace_separated_rule_tokens:
            # ignore all after first ';'
            try:
                i = whitespace_separated_rule_tokens.index(';')
            except ValueError:
                pass
            else:
                whitespace_separated_rule_tokens = whitespace_separated_rule_tokens[:i]

            # all tokens before first ':' are targets
            try:
                i = whitespace_separated_rule_tokens.index(':')
            except ValueError:
                raise ValueError(f"missing ':' in rule ending on line {lineno0 + 1}") from None
            targets = whitespace_separated_rule_tokens[:i]
            for t in targets:
                if '%' in t:
                    raise ValueError(f"pattern in rule ending on line {lineno0 + 1}")  # valid but unsupported
            whitespace_separated_rule_tokens = whitespace_separated_rule_tokens[i + 1:]

            try:
                whitespace_separated_rule_tokens.index(':')
            except ValueError:
                pass
            else:
                # may be valid in double-colon rule or pattern rule
                raise ValueError(f"multiple ':' in line {lineno0 + 1}") from None

            rule_sources.append(whitespace_separated_rule_tokens)
            whitespace_separated_rule_tokens = []

    if to_be_continued:
        raise ValueError("ends with '\\'")

    return rule_sources


def additional_sources_from_rule(lines: Iterable[str]) -> List[str]:
    # Extract source paths of the first Make rule in *lines* and return a list of its source paths without the
    # first one.
    # Expects exactly one rule in *line*.

    rule_sources = sources_from_rules(lines)
    if len(rule_sources) != 1:
        raise ValueError(f"needs exactly one rule, got {len(rule_sources)}")

    rule_source = rule_sources[0]
    if len(rule_source) < 1:
        raise ValueError(f"needs at least one source in rule")

    return rule_source[1:]
