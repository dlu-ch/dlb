# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""The language C and its tools."""

import sys
import re
import dlb.ex
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
