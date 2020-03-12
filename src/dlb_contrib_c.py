# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""The language C and its tools."""

import sys
import string
import re
import dlb.fs
import dlb.ex
from typing import Optional
assert sys.version_info >= (3, 7)


# ISO/IEC 9899:1999 (E), section 6.4.2.1, 5.2.4.1
# for internal identifiers longer than 63 characters, the compiler behaviour if undefined by ISO/IEC 9899:1999 (E)
# for external identifiers longer than 31 characters, the compiler behaviour if undefined by ISO/IEC 9899:1999 (E)
IDENTIFIER = re.compile(r'^[_A-Za-z][_A-Za-z0-9]{0,62}$')  # without universal characters

# Indentifier part of function-like macro (for object-like macro: use IDENTIFIER).
# Example: 'V(a, ...)'
FUNCTIONLIKE_MACRO = re.compile((
    r'^(?P<name>{identifier})'  # without universal characters
    r'\((?P<arguments>(( *{identifier} *,)* *({identifier}|\.\.\.))? *)\)$'
).format(identifier='[_A-Za-z][_A-Za-z0-9]{0,62}'))


def string_literal_from_bytes(text: bytes, max_line_length: Optional[int] = None) -> str:
    # Return a character string literal for *text*, containing only printable ASCII characters except '`'" and no
    # trigraph sequences.
    #
    # If *max_line_length* is not None, the string literal is broken into lines of at most *max_line_length* characters
    # without the line separator. (The minimum source line length a compliant compiler/preprocessor can handle is
    # at least 4095 characters.)

    # ISO/IEC 9899:1999 (E), section 5.2.4.1:
    #
    #   The implementation shall be able to translate and execute at least one program that contains at least one
    #   instance of every one of the following limits: [...]
    #
    #    - 4095 characters in a logical source line
    #    - 4095 characters in a character string literal or wide string literal (after concatenation)

    lines = []
    line = '"'

    break_with_hexdigit = False

    # ISO/IEC 9899:1999 (E), section 5.2.1
    for b in text:
        break_before = False
        if not (0x20 <= b < 0x7F) or b in b'"\\`':
            # avoid non-printable, '"' (for easier parsing) and "`" (for easier reading)
            c = f'\\x{b:02X}'
        else:
            # note: all trigraph sequences start with '??'
            if (break_with_hexdigit and b in bytes(string.hexdigits, 'ascii')) or (b == 0x3F and line[-1:] == '?'):
                break_before = True
            c = chr(b)

        if max_line_length is not None and len(line) + len(c) + 3 * int(break_before) >= max_line_length:
            line += '"'
            if len(line) > 2:
                lines.append(line)
            line = '"'
        elif break_before:
            line += '" "'
        line += c
        break_with_hexdigit = c[:1] == '\\'

    line += '"'
    if not lines or len(line) > 2:
        lines.append(line)

    return '\n'.join(lines)


def _encode_integer(n: int) -> str:
    # first character is decimal digit, all other are upper-case ASCII letters
    i, d = divmod(n, len(string.digits))
    s = string.digits[d]
    while i > 0:
        i, d = divmod(i - 1, len(string.ascii_uppercase))
        s += string.ascii_uppercase[d]
    return s  # length is <= 2 for n <= 269


def identifier_like_from_string(text: str, sep: str = '_') -> str:
    # Return an string that uniquely encodes *text* with the characters 'A' ... 'Z', 'a' ... 'z', '0' .. '9' and '_'.
    # Note: May start with a decimal digit.
    #
    # The character *sep* is treated as input separator and represented as '_' in the return value.

    # Idea similar to Punycode.

    previous_replaced_underscore_index = -1
    underscore_index = 0
    replaced = []

    # replace all except base_characters
    encoded_text = ''
    for c in text:
        if c in string.ascii_letters + string.digits:
            encoded_text += c
        elif c == sep:
            encoded_text += '_'
            underscore_index += 1
        else:
            replaced.append((underscore_index - previous_replaced_underscore_index - 1, ord(c)))
            previous_replaced_underscore_index = underscore_index
            encoded_text += '_'
            underscore_index += 1

    # after the last '_', all (position, codepoint) tuples are encoded with 'A' - 'Z', '0' - '9'
    encoded_text += '_'
    for i, o in replaced:
        encoded_text += _encode_integer(i) + _encode_integer(o)

    return encoded_text


def identifier_from_path(path: dlb.fs.PathLike, *, to_upper_case: bool = True) -> str:
    path = dlb.fs.Path(path)
    if path.is_absolute():
        raise ValueError("'path' must be relative")

    p = path.as_string()
    if p == './':
        p = ''

    if to_upper_case:
        p = p.upper()
    return identifier_like_from_string(p, '/')


# noinspection PyAbstractClass
class CCompiler(dlb.ex.Tool):

    # Definition of object-like macros (like '#define VERSION 1.2.3') and function-like macros (like '#define V(x) #x').
    # If value is not None: define the definition with the value as the macro's replacement list.
    # If value is None: "undefine" the definition.
    DEFINITIONS = {}  # e.g. {'VERSION': '1.2.3', 'MAX(a, b)': '(((a) > (b)) ? (a) : (b))'}

    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False)

    # tuple of paths of directories that are to be searched for include files in addition to the system include files
    include_search_directories = dlb.ex.Tool.Input.Directory[:](required=False)

    # paths of all files in the managed tree directly or indirectly included by *source_file*
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

    # path of compiler executable
    compiler_executable = dlb.ex.Tool.Input.RegularFile(explicit=False)


class GenerateHeaderFile(dlb.ex.Tool):
    # Generates a file to be includes with '#include'.
    # Contains include guards based

    INCLUDE_GUARD_PREFIX = ''
    INCLUDE_GUARD_SUFFIX = '_'

    PATH_COMPONENTS_TO_STRIP = 0  # number of leading path component to strip for include guard

    file = dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False)

    def write_preamble(self, open_file):
        open_file.write('// This file was created automatically.\n// Do not modify it manually.\n\n')

    def write_content(self, open_file):
        pass

    async def redo(self, result, context):
        if not IDENTIFIER.match(self.INCLUDE_GUARD_PREFIX + self.INCLUDE_GUARD_SUFFIX):
            raise ValueError("'INCLUDE_GUARD_PREFIX' and 'INCLUDE_GUARD_SUFFIX' do not form a valid identifier")
        if self.PATH_COMPONENTS_TO_STRIP >= len(result.file.parts):
            raise ValueError("nothing left to strip after 'PATH_COMPONENT_TO_STRIP'")

        with context.temporary() as tmp_file:
            include_guard = identifier_from_path(result.file[self.PATH_COMPONENTS_TO_STRIP:])
            include_guard = self.INCLUDE_GUARD_PREFIX + include_guard + self.INCLUDE_GUARD_SUFFIX

            with open(tmp_file.native, 'w', encoding='utf-8') as open_file:
                self.write_preamble(open_file)
                open_file.write(f'#ifndef {include_guard}\n#define {include_guard}\n\n')
                self.write_content(open_file)
                open_file.write(f'\n#endif  // {include_guard}\n')
            context.replace_output(result.file, tmp_file)
