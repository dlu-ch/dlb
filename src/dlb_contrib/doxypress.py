# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Generate documents from source code with DoxyPress."""

# DoxyPress: <https://github.com/copperspice/doxypress/>
# Tested with: DoxyPress 1.3.8
# Executable: 'doxypress'
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.doxypress
#
#   with dlb.ex.Context():
#       dlb_contrib.doxypress.DoxyPress(
#           # contains '${{source_directories}}', '${{output_directory}}':
#           project_template_file='doxypress.json',
#           source_directories=['src/'],  # replaces '${{source_directories}}' in project file
#           output_directory='build/out/'
#       ).start()

__all__ = ['PLACEHOLDER_NAME_REGEX', 'Template', 'DoxyPress']


# Example content of minimal project template file:
#
#   {
#       "doxypress-format": 1,
#
#       "input": {
#           "input-source": ${{source_directories}},
#           "input-patterns": ["*.cpp", "*.hpp"],
#           "input-recursive": true,
#       },
#
#       "output": {
#           "output-dir": ${{output_directory}},
#           "strip-from-inc-path": ${{source_directories}},
#           "strip-from-path": ${{source_directories}},
#       }
#   }

import sys
import re
import string
import collections.abc
import json
from typing import Any, Dict

import dlb.fs
import dlb.ex

assert sys.version_info >= (3, 7)

PLACEHOLDER_NAME_REGEX = re.compile(r'^[A-Za-z_][A-Za-z_0-9]*$')


class Template(string.Template):  # like dlb_contrib.doxygen.Template
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


def _transform_value(context, value):
    if value is None:
        return
    if isinstance(value, (int, str)):
        return value
    if isinstance(value, dlb.fs.Path):
        if not value.is_absolute():
            # Paths in the project file are relative to the directory of project file,
            # so do not use relative paths
            value = context.root_path / value
        return str(value.native)
    if isinstance(value, bytes):
        raise TypeError
    if isinstance(value, collections.abc.Iterable):
        return [_transform_value(context, v) for v in value]
    raise TypeError


def _transform_replacement(context, replacements: Dict[str, Any]):
    d = {}
    for name, value in replacements.items():
        if not isinstance(name, str):
            raise TypeError('placeholder name must be str')
        if not PLACEHOLDER_NAME_REGEX.match(name):
            raise ValueError(f'invalid placeholder name: {name!r}')
        d[name] = json.dumps(_transform_value(context, value))
        # DoxyPress parses the project file with QJsonDocument::fromJson(file.readAll())
    return d


class DoxyPress(dlb.ex.Tool):
    # Generate documentation from source files with DoxyPress, using a project file generated from a
    # project template file *project_template_file* by replacing (unescaped) placeholders according to
    # *TEXTUAL_REPLACEMENTS*.
    #
    # The *project_template_file* should a least contain the following lines:
    #
    #     "input-source": ${{source_directories}},
    #     "output-dir": ${{output_directory}},

    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'doxypress'

    # Command line parameters for *EXECUTABLE* to output version information on standard output
    VERSION_PARAMETERS = ('--version',)

    # Placeholders in DoxyPress project file template.
    # The dictionary key are placeholder names and the value their replacement value.
    #
    # The name of a placeholder must be a non-empty string from ASCII letters, decimal digits and '_' that does not
    # start with a decial digit.
    #
    # The replacement value can be None, bool, int, a dlb.fs.Path, a non-nested iterable or anything a str can be
    # constructed from.
    # A dlb.fs.Path object *p* is replaced by str(q.native), where *q* is the absolute path for *q*.
    #
    # The dictionary items for placeholder name equal to a name of dependency role are ignored.
    # Can be modified by overwriting *get_replacements()*.
    TEXTUAL_REPLACEMENTS = {}

    # When any if these change: redo.
    source_files_to_watch = dlb.ex.input.RegularFile[:](required=False)

    source_directories = dlb.ex.input.Directory[1:]()

    # Template for DoxyPress project file, UTF-8 encoded.
    # Escape $ by $$.
    # All unescaped occurences of ${{name}} are replaced by the content of TEXTUAL_REPLACEMENTS[name].
    project_template_file = dlb.ex.input.RegularFile()

    output_directory = dlb.ex.output.Directory()

    def get_replacements(self) -> Dict[str, Any]:
        # Return dictionary of replacements.
        # See TEXTUAL_REPLACEMENTS for details.
        return self.TEXTUAL_REPLACEMENTS

    async def redo(self, result, context):
        # DoxyPress's project file is always UTF-8 encoded
        with open(result.project_template_file.native, 'rb') as f:
            projectfile_template = f.read().decode()  # preserve line separators

        with context.temporary() as projectfile, context.temporary(is_dir=True) as output_directory:
            replacements = self.get_replacements()

            replacements['output_directory'] = output_directory
            for name in ('source_directories', 'project_template_file', 'source_files_to_watch'):
                replacements[name] = getattr(result, name)
            replacements = _transform_replacement(context, replacements)

            try:
                projectfile_content = Template(projectfile_template).substitute(replacements)
            except KeyError as e:
                name = e.args[0]
                msg = (
                    f"unexpanded placeholder in project file template "
                    f"{result.project_template_file.as_string()!r}\n"
                    f"  | file contains '${{{{{name}}}}}' but 'TEXTUAL_REPLACEMENTS' does not define a replacement"
                )
                raise ValueError(msg) from None

            with open(projectfile.native, 'wb') as f:
                f.write(projectfile_content.encode())  # preserve line separators

            await context.execute_helper(self.EXECUTABLE, [projectfile])
            context.replace_output(result.output_directory, output_directory)
