# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Process backslash escape sequences (Python, Bash, Git, ...)."""

# Usage example:
#
#   import dlb_contrib.backslashescape
#
#   s = b'"tmp/x\\076y"'
#   ... = dlb_contrib.backslashescape.unquote(s)  # b'tmp/x\076y'

__all__ = ['PYTHON_ESCAPES', 'unquote', 'unquote_octal']

import sys
import string
from typing import AnyStr, Dict, Optional

assert sys.version_info >= (3, 7)


PYTHON_ESCAPES = {
    '"': 0x22,  # U+0022 QUOTATION MARK
    "'": 0x27,  # U+0027 APOSTROPHE
    'a': 0x07,  # U+0007 ALERT
    'b': 0x08,  # U+0008 BACKSPACE
    'f': 0x0C,  # U+000C FORM FEED
    'n': 0x0A,  # U+000A LINE FEED
    'r': 0x0D,  # U+000D CARRIAGE RETURN
    't': 0x09,  # U+0009 CHARACTER TABULATION
    'v': 0x0B   # U+000B LINE TABULATION
}


def unquote(literal: AnyStr, replacement_by_escaped_character: Dict[str, int] = PYTHON_ESCAPES,
            with_hex: bool = True, with_oct: bool = True,
            opening: Optional[str] = '"', closing: Optional[str] = None) -> AnyStr:
    # Return an unquoted version of the backslash-quoted *literal* with the same type as *literal*
    # (backslash: U+005C REVERSE SOLIDUS).
    #
    # If *opening* is not None, *literal* must start with *opening* and end with *closing* (or *opening*
    # if *closing* is None), and each occurrence of *opening* and *closing* between must be escaped with a preceding
    # (unescaped) backslash.
    #
    # A backslash followed by a backslash is replaced by a single backslash.
    # A backslash followed by character *c* is replaced by the character with codepoint
    # 'replacement_by_escaped_character[c]' if *c* is in *replacement_by_escaped_character*.
    #
    # If *with_octal* is True, a backslash followed by one to three octal digits ('0' ... '7') is replaced by the
    # character with the corresponding codepoint.
    # If *with_hex* is True, a backslash followed by 'x' and one or two least hexdecimal digits ('0' ... '9',
    # 'a' ... 'f', 'A' .. 'F') is replaced by the character with the corresponding codepoint.

    if isinstance(literal, bytes):
        def to_chr(c):
            return chr(c)

        def to_literal(i):
            return bytes([i])

        empty = b''
    elif isinstance(literal, str):
        def to_chr(c):
            return c

        def to_literal(i):
            return chr(i)

        empty = ''
    else:
        raise TypeError("'literal' must be a str or bytes")

    if opening is not None:
        if not isinstance(opening, str):
            raise TypeError("'opening' must be None or a string")
        if len(opening) != 1:
            raise ValueError("'opening' must contain exactly one character")

    if closing is None:
        closing = opening
    else:
        if not isinstance(closing, str):
            raise TypeError("'closing' must be None or a string")
        if len(closing) != 1:
            raise ValueError("'closing' must contain exactly one character")

    if opening:
        if len(literal) < 2 or to_chr(literal[0]) != opening or to_chr(literal[-1]) != closing:
            raise ValueError(f"'literal' not delimited by {opening!r} and {closing!r}: {literal!r}")

        def checked_part(part):
            for c in {opening, closing}:
                if to_literal(ord(c)) in part:
                    raise ValueError(f"'literal' must not contain an unescaped {c!r}: {literal!r}")
            return part

        between = literal[1:-1]
    else:
        def checked_part(part):
            return part

        between = literal

    parts = between.split(to_literal(0x5C))
    unquoted_parts = [checked_part(parts[0])]
    i = 1
    while i < len(parts):
        p = parts[i]
        if p:
            c = to_chr(p[0])
            if c in replacement_by_escaped_character:
                unquoted_parts.append(to_literal(replacement_by_escaped_character[c]) + checked_part(p[1:]))
            elif with_oct and c in string.digits:
                # Octal: exactly 3 octal digits or less than 3 octal digits not followed by an octal digit
                n = 1
                while n < 3 and n < len(p) and to_chr(p[n]) in string.digits:
                    n += 1
                unquoted_parts.append(to_literal(int(p[:n], 8)) + checked_part(p[n:]))
            elif with_hex and c == 'x':
                # Hexadecimal: exactly 2 hexadecimal digits or less than 2 hexadecimal digits not followed by
                # a hexadecimal digit.
                # Note: this is not suitable to decode C and C++ literals, because C and C++ do not restrict the number
                # of hexadecimal digit.
                n = 1
                while n < 3 and n < len(p) and to_chr(p[n]) in string.hexdigits:
                    n += 1
                if n < 2:
                    raise ValueError(f"truncated \\xXX escape sequence")
                unquoted_parts.append(to_literal(int(p[1:n], 16)) + checked_part(p[n:]))
            else:
                e = f'\\{c}'
                raise ValueError(f"unknown escape sequence: {e!r}")
        else:
            unquoted_parts.append(to_literal(0x5C))
            if i + 1 >= len(parts):
                raise ValueError(f"truncated escape sequence")
            if not parts[i + 1]:
                i += 1  # is escaped backslash at end of string
        i += 1

    return empty.join(unquoted_parts)


def unquote_octal(literal: AnyStr) -> AnyStr:
    return unquote(literal, replacement_by_escaped_character={}, with_hex=False, with_oct=True,
                   opening=None, closing=None)


# Bash (https://www.gnu.org/savannah-checkouts/gnu/bash/manual/bash.html#ANSI_002dC-Quoting):
#
#     \a          alert (bell)
#     \b          backspace
#     \e, \E      an escape character
#     \f          form feed
#     \n          new line
#     \r          carriage return
#     \t          horizontal tab
#     \v          vertical tab
#     \\          backslash
#     \'          single quote
#     \"          double quote
#     \?          question mark
#     \nnn        the  eight-bit  character  whose value is the octal value nnn (one to three octal digits)
#     \xHH        the eight-bit character whose value  is  the  hexadecimal value HH (one or two hex digits)
#     \uHHHH      the  Unicode (ISO/IEC 10646) character whose value is the hexadecimal value HHHH
#                 (one to four hex digits)
#     \UHHHHHHHH  the Unicode (ISO/IEC 10646) character whose value is the hexadecimal value HHHHHHHH
#                 (one to eight hex digits)
#     \cx         a control-x character
#
# Python (https://docs.python.org/3/reference/lexical_analysis.html#string-and-bytes-literals):
#
#     \\          Backslash (\)
# 	  \'          Single quote (')
# 	  \"          Double quote (")
# 	  \a          ASCII Bell (BEL)
# 	  \b          ASCII Backspace (BS)
# 	  \f          ASCII Formfeed (FF)
# 	  \n          ASCII Linefeed (LF)
# 	  \r          ASCII Carriage Return (CR)
# 	  \t          ASCII Horizontal Tab (TAB)
# 	  \v          ASCII Vertical Tab (VT)
# 	  \ooo        Character with octal value ooo (as in Standard C, up to three octal digits are accepted)
#     \xhh        Character with hex value hh (unlike in Standard C, exactly two hex digits are required)
#     \N{name}    in string literals only: Character named name in the Unicode database
#     \uxxxx      in string literals only: Character with 16-bit hex value xxxx
#     \Uxxxxxxxx  in string literals only: Character with 32-bit hex value xxxxxxxx
#
# Rust (https://doc.rust-lang.org/reference/tokens.html):
#
#     \'          Single quote
#     \"          Double quote
#     \n          Newline
#     \r          Carriage return
#     \t          Tab
#     \\          Backslash
#     \0          Null
#     \x7F        8-bit character code (exactly 2 digits)
#     \u{7FFF}	  24-bit Unicode character code (up to 6 digits)
#
# Git path output (https://github.com/git/git/blob/v2.20.1/quote.c#L191):
#
#     \\          Backslash (\)
# 	  \"          Double quote (")
# 	  \a          ASCII Bell (BEL)
# 	  \b          ASCII Backspace (BS)
# 	  \f          ASCII Formfeed (FF)
# 	  \n          ASCII Linefeed (LF)
# 	  \r          ASCII Carriage Return (CR)
# 	  \t          ASCII Horizontal Tab (TAB)
# 	  \v          ASCII Vertical Tab (VT)
# 	  \ooo        Character with octal value ooo (exactly three digits)
