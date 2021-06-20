# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Check elements of the syntax, generate code and build compilers and linkers with a common interface
for the C language family."""

# C:   ISO/IEC 9899:1999 (E)
# C++: ISO/IEC 14882:1998 (E)
#
# Usage example:
#
#  import dlb.ex
#  import dlb_contrib.clike
#
#  name = ...
#  assert dlb_contrib.clike.SIMPLE_IDENTIFIER_REGEX.match(name)
#
#  ... = dlb_contrib.clike.string_literal_from_bytes('Tête-à-tête'.encode())
#  # '"T\\xC3\\xAAte-\\xC3\\xA0-t\\xC3\\xAAte"'
#
#  class GenerateVersionFile(dlb_contrib.clike.GenerateHeaderFile):
#      WD_VERSION = ...
#
#      def write_content(self, file):
#          wd_version = \
#              dlb_contrib.clike.string_literal_from_bytes(self.WD_VERSION.encode())
#          file.write(f'\n#define APPLICATION_VERSION {wd_version}\n')
#
#  class CCompiler(dlb_contrib.clike.ClikeCompiler):
#      EXECUTABLE = 'specific-cc'
#
#      async def redo(self, result, context):
#          if len(result.object_files) > len(result.source_files):
#              raise ValueError("'object_files' must be of at most the same length as 'source_files'")
#          optional_object_files = result.object_files + (None,) * (len(result.source_files) - len(result.object_files))
#
#          included_files = set()
#          for source_file, optional_object_file in zip(result.source_files, optional_object_files):
#              with context.temporary() as temp_object_file:
#                  await context.execute_helper(self.EXECUTABLE, ...,
#                                               '-o', temp_object_file, source_file)
#                  included_files |= ...
#                  if optional_object_file is not None:
#                      context.replace_output(optional_object_file, temp_object_file)
#          result.included_files = sorted(included_files)
#
#  with dlb.ex.Context():
#      GenerateVersionFile(file='Version.h').start()
#      CCompiler(source_files=['main.c'], object_files=['main.c.o']).start()

__all__ = [
    'SIMPLE_IDENTIFIER_REGEX', 'IDENTIFIER_REGEX', 'PORTABLE_C_IDENTIFIER_REGEX', 'FUNCTIONLIKE_MACRO_REGEX',
    'string_literal_from_bytes', 'identifier_like_from_string', 'identifier_from_path',
    'ClikeCompiler', 'GenerateHeaderFile'
]

import sys
import string
import re
from typing import List, Optional, Union

import dlb.fs
import dlb.cf
import dlb.di
import dlb.ex

assert sys.version_info >= (3, 7)

# Identifier of unrestricted length without universal characters.
#
# C - ISO/IEC 9899:1999 (E), section 6.4.2.1, 5.2.4.1:
# For internal identifiers longer than 63 characters and external identifiers longer than 31 characters, the compiler
# behaviour is undefined.
#
# C++ - ISO/IEC 14882:1998 (E), section 2.10:
# An identifier is an arbitrarily long sequence [...].
# All characters are significant.
#
# Note: not each string matching this regular expression is a valid identifier (could by keyword).
SIMPLE_IDENTIFIER_REGEX = re.compile(r'^[_A-Za-z][_A-Za-z0-9]*$')

# Identifier of unrestricted length without universal characters.
# Note: not each string matching this regular expression is a valid identifier (could by keyword or invalid
# universal characters),
IDENTIFIER_REGEX = re.compile(r'^[_A-Za-z]([_A-Za-z0-9]|\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8})*$')

# Simple internal or external identifier with only significant characters for a compliant C compiler
PORTABLE_C_IDENTIFIER_REGEX = re.compile(r'^[_A-Za-z][_A-Za-z0-9]{0,30}$')

# Indentifier part of function-like macro (for object-like macro: use IDENTIFIER_REGEX).
# Example: 'V(a, ...)'
FUNCTIONLIKE_MACRO_REGEX = re.compile((
    r'^(?P<name>{identifier})'  # without universal characters
    r'\((?P<arguments>(( *{identifier} *,)* *({identifier}|\.\.\.))? *)\)$'
).format(identifier='[_A-Za-z][_A-Za-z0-9]*'))


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

    hexdigits = bytes(string.hexdigits, 'ascii')
    break_with_hexdigit = False

    # ISO/IEC 9899:1999 (E), section 5.2.1
    for b in text:
        break_before = False
        if not (0x20 <= b < 0x7F) or b in b'"\\`':
            # avoid non-printable, '"' (for easier parsing) and "`" (for easier reading)
            c = f'\\x{b:02X}'
        else:
            # note: all trigraph sequences start with '??'
            if (break_with_hexdigit and b in hexdigits) or (b == 0x3F and line[-1:] == '?'):
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
    # first character is decimal digit, all others are upper-case ASCII letters
    i, d = divmod(n, len(string.digits))
    s = string.digits[d]
    while i > 0:
        i, d = divmod(i - 1, len(string.ascii_uppercase))
        s += string.ascii_uppercase[d]
    return s  # length is <= 2 for n <= 269


def identifier_like_from_string(text: str, sep: str = '_') -> str:
    # Return a string that uniquely encodes *text* with the characters 'A' - 'Z', 'a' - 'z', '0' - '9' and '_'.
    # Note: May be empty and may start with a decimal digit.
    #
    # The character *sep* is treated as input separator and represented as '_' in the return value.

    # Idea similar to Punycode.

    previous_replaced_underscore_index = -1
    underscore_index = 0
    replaced = []

    # replace all except string.ascii_letters + string.digits
    encoded_text = ''
    for c in text:
        if c in string.ascii_letters + string.digits:
            encoded_text += c
        else:
            if c != sep:
                replaced.append((underscore_index - previous_replaced_underscore_index - 1, ord(c)))
                previous_replaced_underscore_index = underscore_index
            encoded_text += '_'
            underscore_index += 1

    # after the last '_', all (position_different, codepoint) tuples are encoded with 'A' - 'Z', '0' - '9'
    if underscore_index:
        encoded_text += '_' + ''.join(_encode_integer(d) + _encode_integer(o) for d, o in replaced)

    return encoded_text


def identifier_from_path(path: dlb.fs.PathLike, *, to_upper_case: bool = True) -> str:
    # Examples:
    #
    #    >>> identifier_from_path('hello')
    #    'HELLO'
    #
    #    >>> identifier_from_path('string.h')
    #    'STRING_H_06D'
    #
    #    >>> identifier_from_path('core/api-version.h')
    #    'CORE_API_VERSION_H_15D06D'

    path = dlb.fs.Path(path)
    if path.is_absolute():
        raise ValueError("'path' must be relative")

    p = path.as_string()
    if to_upper_case:
        p = p.upper()
    return identifier_like_from_string(p, '/')


# noinspection PyAbstractClass
class ClikeCompiler(dlb.ex.Tool):
    # Compile one or multiple source file to their corresponding object files.

    # Dynamic helper of compiler executable, looked-up in the context.
    EXECUTABLE = ''  # define in subclass

    # Definition of object-like macros (like '#define VERSION 1.2.3') and function-like macros (like '#define V(x) #x').
    # If value is not None: define the definition with the value as the macro's replacement list.
    # If value is None: "undefine" the definition.
    DEFINITIONS = {}  # e.g. {'VERSION': '1.2.3', 'MAX(a, b)': '(((a) > (b)) ? (a) : (b))'}

    source_files = dlb.ex.input.RegularFile[1:]()

    # If i < len(object_files): object_files[i] is object file for source_files[i].
    # Otherwise: there is no object corresponding file for source_files[i].
    object_files = dlb.ex.output.RegularFile[0:](replace_by_same_content=False)

    # Tuple of paths of directories that are to be searched for include files in addition to the system include files.
    include_search_directories = dlb.ex.input.Directory[:](required=False)

    # Paths of all files in the managed tree directly or indirectly included by *source_file*.
    included_files = dlb.ex.input.RegularFile[:](explicit=False)

    def get_extra_compile_arguments(self) -> List[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        # Return list of additional commandline arguments for *EXECUTABLE*.
        return []

    @classmethod
    def does_source_compile(cls, source: str) -> bool:
        # Check whether *source* compiles without (fatal) errors.
        #
        # Every occurrence of dlb.ex.HelperExecutionError is consideres a compilation error and suppressed.
        # Every other raise exception is considered as unrelated to the compilation.
        #
        # Use for concrete subclasses of this class, e.g. dlb_contrib.gcc.CCompilerGcc.
        #
        # Example:
        #    >>> with dlb.ex.Context(): dlb_contrib.gcc.CCompilerGcc.does_source_compile('#include <stdint.h>')
        #    True
        #    >>> with dlb.ex.Context(): dlb_contrib.gcc.CCompilerGcc.does_source_compile('#include "does/not/exist"')
        #    False

        with dlb.ex.Context.active.temporary() as s, dlb.ex.Context.active.temporary():
            with open(s.native, 'w', encoding='utf-8') as f:
                f.write(source + '\n')

            with dlb.ex.Context():  # complete redos with previous message levels
                pass

            old_level_level_redo_reason = dlb.cf.level.redo_reason
            old_level_redo_start = dlb.cf.level.redo_start
            old_execute_helper_inherits_files_by_default = dlb.cf.execute_helper_inherits_files_by_default
            try:
                dlb.cf.execute_helper_inherits_files_by_default = False
                dlb.cf.level.redo_reason = dlb.di.DEBUG
                dlb.cf.level.redo_start = dlb.di.DEBUG
                cls(source_files=[s], object_files=[]).start(force_redo=True).complete()
                return True
            except dlb.ex.HelperExecutionError:
                return False
            finally:
                dlb.cf.execute_helper_inherits_files_by_default = old_execute_helper_inherits_files_by_default
                dlb.cf.level.redo_reason = old_level_level_redo_reason
                dlb.cf.level.redo_start = old_level_redo_start

    @classmethod
    def check_constant_expression(cls, constant_expression: str, *,
                                  preamble: str = '',
                                  by_preprocessor: bool = True,
                                  by_compiler: bool = True,
                                  check_syntax: bool = True) -> Optional[bool]:
        # Check whether *constant_expression* is non-zero when evaluated the preprocessor or the actual compiler.
        #
        # *preamble* is prependend (and separated by a new line) to the source code for the evaluation
        # of *constant_expression*.
        #
        # If *check_syntax* is True, the negated *constant_expression* is also checked. If its result is not the
        # negated result of *constant_expression*, *None* is returned.
        #
        # If *constant_expression* consists only of white space (space, HT, CR, LF), *None* is returned.
        #
        # If *by_preprocessor* is True, *constant_expression* is checked by the preprocessor ('#if' directive).
        # If *by_compiler* is True, *constant_expression* is checked by the compiler after preprocessing.
        # If *by_preprocessor* and *by_compiler* are both False, *None* is returned.
        #
        # Use for concrete subclasses of this class, e.g. dlb_contrib.gcc.CCompilerGcc.
        #
        # Example:
        #    >>> with dlb.ex.Context(): dlb_contrib.gcc.CCompilerGcc.check_constant_expression('1 < 2')
        #    True
        #    >>> with dlb.ex.Context(): dlb_contrib.gcc.CCompilerGcc.check_constant_expression('1 <')
        #    None
        #    >>> with dlb.ex.Context():
        #    ... dlb_contrib.gcc.CCompilerGcc.check_constant_expression('UINT_LEAST8_MAX <= UINT_LEAST16_MAX',
        #    ...                                                        preamble='#include <stdint.h>')
        #    True

        if not isinstance(constant_expression, str):
            raise TypeError("'constant_expression' must be a str")
        if not isinstance(preamble, str):
            raise TypeError("'preamble' must be a str")

        constant_expression = constant_expression.strip(' \t\r\n')
        preamble = preamble.strip(' \t\r\n')

        tmpl = ''
        if by_compiler:
            tmpl += '\nstruct main {{ char main[{0} ? 1 : -1]; }};'
        if by_preprocessor:
            tmpl += '\n#if !{0}\n#error\n#endif'
            # - undefined identifiers (except 'defined') are replaced by 0
            # - may be undefined if expression contains 'defined' after or before macro replacement
            # - all integer types act as if they have the same representation as intmax_t
            #   (for all signed integer types) or uintmax_t (for all unsigned integer types),

        if not (constant_expression and tmpl):
            return

        positive_result = cls.does_source_compile(preamble + tmpl.format(f'({constant_expression})'))
        if not check_syntax:
            return positive_result
        negative_result = cls.does_source_compile(preamble + tmpl.format(f'!({constant_expression})'))
        if (not negative_result) == positive_result:
            return positive_result

    @classmethod
    def get_size_of(cls, expression: str, *, preamble: str = '') -> Optional[int]:
        # Returns size of expression *expression* (as returned by 'sizeof' operator) or *None* if it cannot be
        # determined.
        #
        # *preamble* is prependend (and separated by a new line) to the source code for evaluation of
        # 'sizeof' *expression*.
        #
        # Use for concrete subclasses of this class, e.g. dlb_contrib.gcc.CCompilerGcc.
        #
        # Example:
        #    >>> with dlb.ex.Context(): dlb_contrib.gcc.CCompilerGcc.get_size_of('char[10]')
        #    10

        if not isinstance(preamble, str):
            raise TypeError("'preamble' must be a str")

        maximum = 1
        while True:
            previous_maximum = maximum
            maximum = 2 * (maximum + 1) - 1
            r = cls.check_constant_expression(
                f'sizeof({expression}) > {maximum}u && {maximum}u > {previous_maximum}u',
                preamble=preamble, by_preprocessor=False, check_syntax=False)
            if not r:
                break

        # sizeof(...) <= maximum
        # or maximum is the largest representable unsigned integer of the form 2^i - 1 for integer n
        # or something is wrong with *expression* or *preamble*
        r = cls.check_constant_expression(
                f'sizeof({expression}) > {maximum}u',
                preamble=preamble, by_preprocessor=False)
        if not (r is False):
            return

        minimum = 1
        while True:
            n = (minimum + maximum) // 2
            if n >= maximum:
                break

            # minimum <= n < maximum
            if cls.check_constant_expression(f'sizeof({expression}) <= {n}u',
                                             preamble=preamble, by_preprocessor=False, check_syntax=False):
                maximum = n
            else:
                minimum = n + 1

        return n


class GenerateHeaderFile(dlb.ex.Tool):
    # Generates a file to be included with '#include'.
    # Contains include guards based on *file*.

    INCLUDE_GUARD_PREFIX = ''
    INCLUDE_GUARD_SUFFIX = '_'

    PATH_COMPONENTS_TO_STRIP = 0  # number of leading path component to strip for include guard

    output_file = dlb.ex.output.RegularFile(replace_by_same_content=False)

    def write_preamble(self, file):
        file.write('// This file was created automatically.\n// Do not modify it manually.\n')

    def write_content(self, file):
        pass

    async def redo(self, result, context):
        if not SIMPLE_IDENTIFIER_REGEX.match(self.INCLUDE_GUARD_PREFIX + self.INCLUDE_GUARD_SUFFIX):
            raise ValueError("'INCLUDE_GUARD_PREFIX' and 'INCLUDE_GUARD_SUFFIX' do not form a valid identifier")
        if self.PATH_COMPONENTS_TO_STRIP >= len(result.output_file.parts):
            raise ValueError("nothing left to strip after 'PATH_COMPONENTS_TO_STRIP'")

        with context.temporary() as tmp_file:
            include_guard = identifier_from_path(result.output_file[self.PATH_COMPONENTS_TO_STRIP:])
            include_guard = self.INCLUDE_GUARD_PREFIX + include_guard + self.INCLUDE_GUARD_SUFFIX

            with open(tmp_file.native, 'w', encoding='utf-8') as file:
                self.write_preamble(file)
                file.write(f'\n#ifndef {include_guard}\n#define {include_guard}\n')
                self.write_content(file)
                file.write(f'\n#endif  // {include_guard}\n')
            context.replace_output(result.output_file, tmp_file)
