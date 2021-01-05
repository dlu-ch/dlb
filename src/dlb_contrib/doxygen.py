# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Generate documents from source code with Doxygen."""

# Doxygen: <https://www.doxygen.nl/>
# Tested with: Doxygen 1.8.13
# Executable: 'doxygen'
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.doxygen
#
#   with dlb.ex.Context():
#       dlb_contrib.doxygen.Doxygen(
#           # contains '${{source_directories}}', '${{output_directory}}':
#           configuration_template_file='Doxyfile',
#           source_directories=['src/'],  # replaces '${{source_directories}}' in Doxyfile
#           output_directory='build/out/'
#       ).start()

__all__ = ['PLACEHOLDER_NAME_REGEX', 'Template', 'Path', 'Doxygen']

import sys
import re
import string
import collections.abc
from typing import Any, Dict

import dlb.fs
import dlb.ex

assert sys.version_info >= (3, 7)

PLACEHOLDER_NAME_REGEX = re.compile(r'^[A-Za-z_][A-Za-z_0-9]*$')


class Path(dlb.fs.PosixPath):
    UNSAFE_CHARACTERS = '\n\r'

    def check_restriction_to_base(self, components_checked: bool):
        if components_checked:
            return
        if any(s in c for c in self.parts for s in self.UNSAFE_CHARACTERS):
            raise ValueError("must not contain these characters: {0}".format(
                ','.join(repr(c) for c in sorted(self.UNSAFE_CHARACTERS))))
        if any('\\"' in c for c in self.parts):
            raise ValueError("must not contain '\\\"'")


class Template(string.Template):
    def __init__(self, template):
        # replace only "${{" <name> "}}" with substitute()
        self.pattern = re.compile(r'\$'
            r'(?:'
              r'(?P<escaped>\$)|'
              r'{{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)}}|'
              r'(?P<named>\$)|'   # always None
              r'(?P<invalid>\$)'  # always None
            r')')
        super(Template, self).__init__(template)


def _escape(s):
    if '\\"' in s or any(c in s for c in '\n\r'):
        # see GetQuotedString in https://github.com/doxygen/doxygen/blob/Release_1_8_13/src/configimpl.l
        raise ValueError(f"not representable in a Doxygen configuration file value: {s!r}")
    return '"{}"'.format(s.replace('"', '\\"'))


def _stringify_value(value, allow_iterable: bool = True):
    if isinstance(value, str):
        return _escape(value)
    if value is None:
        return ''
    if value is False:
        return 'NO'
    if value is True:
        return 'YES'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, dlb.fs.Path):
        return _escape(str(value.native))
    if isinstance(value, collections.abc.Iterable):
        if not allow_iterable:
            raise ValueError('nested iterables not representable in Doxygen configuration file value')
        members = [_stringify_value(e, False) for e in value if value is not None]
        if len(members) <= 1:
            return ''.join(members)
        return ' \\\n    '.join([''] + members)[1:]
    return _escape(str(value))


def _transform_replacement(replacements: Dict[str, Any]):
    d = {}
    for name, value in replacements.items():
        if not isinstance(name, str):
            raise TypeError('placeholder name must be str')
        if not PLACEHOLDER_NAME_REGEX.match(name):
            raise ValueError(f'invalid placeholder name: {name!r}')
        d[name] = _stringify_value(value)
    return d


class Doxygen(dlb.ex.Tool):
    # Generate documentation from source files with Doxygen, using a configuration file generated from a
    # configuration template file *configuration_template_file* by replacing (unescaped) placeholders according to
    # *TEXTUAL_REPLACEMENTS*.
    #
    # The *configuration_template_file* should a least contain the following lines:
    #
    #     INPUT = ${{source_directories}}
    #     OUTPUT_DIRECTORY = ${{output_directory}}

    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'doxygen'

    # Command line parameters for *EXECUTABLE* to output version information on standard output
    VERSION_PARAMETERS = ('--version',)

    # Placeholders in Doxygen configuration file template.
    # The dictionary key are placeholder names and the value their replacement value.
    #
    # The name of a placeholder must be a non-empty string from ASCII letters, decimal digits and '_' that does not
    # start with a decial digit.
    #
    # The replacement value can be None, bool, int, a dlb.fs.Path, a non-nested iterable or anything a str can be
    # constructed from. It must not contain the substring '\\"'.
    # *True* is replaced by 'YES', *False* is replaced by 'NO', *None* is replaced by the empty string, and
    # a dlb.fs.Path object *p* is replaced by str(p.native).
    #
    # The dictionary items for placeholder name equal to a name of dependency role are ignored.
    # Can be modified by overwriting *get_replacements()*.
    TEXTUAL_REPLACEMENTS = {}

    # When any if these change: redo.
    source_files_to_watch = dlb.ex.input.RegularFile[:](required=False, cls=Path)

    source_directories = dlb.ex.input.Directory[1:](cls=Path)

    # Template for Doxygen configuration file, UTF-8 encoded (must contain 'DOXYFILE_ENCODING = UTF-8')
    # Escape $ by $$.
    # All unescaped occurences of ${{name}} are replaced by the content of TEXTUAL_REPLACEMENTS[name].
    configuration_template_file = dlb.ex.input.RegularFile()

    output_directory = dlb.ex.output.Directory(cls=Path)

    def get_replacements(self) -> Dict[str, Any]:
        # Return dictionary of replacements.
        # See TEXTUAL_REPLACEMENTS for details.
        return self.TEXTUAL_REPLACEMENTS

    async def redo(self, result, context):

        with open(result.configuration_template_file.native, 'rb') as f:
            doxyfile_template = f.read().decode()  # preserve line separators

        with context.temporary() as doxyfile, context.temporary(is_dir=True) as output_directory:
            replacements = self.get_replacements()

            replacements['output_directory'] = output_directory
            for name in ('source_directories', 'configuration_template_file', 'source_files_to_watch'):
                replacements[name] = getattr(result, name)
            replacements = _transform_replacement(replacements)

            try:
                doxyfile_content = Template(doxyfile_template).substitute(replacements)
            except KeyError as e:
                name = e.args[0]
                msg = (
                    f"unexpanded placeholder in configuration file template "
                    f"{result.configuration_template_file.as_string()!r}\n"
                    f"  | file contains '${{{{{name}}}}}' but 'TEXTUAL_REPLACEMENTS' does not define a replacement"
                )
                raise ValueError(msg) from None

            with open(doxyfile.native, 'wb') as f:
                f.write(doxyfile_content.encode())  # preserve line separators

            await context.execute_helper(self.EXECUTABLE, [doxyfile])
            context.replace_output(result.output_directory, output_directory)
