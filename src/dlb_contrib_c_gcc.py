# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Support of the language C by the GNU Compiler Collection."""

import sys
from typing import Iterable, Union
import os
import dlb.fs
import dlb_contrib_make
import dlb_contrib_c
assert sys.version_info >= (3, 7)


def check_warning_name(name: str) -> str:
    name = str(name)
    if not name or name.startswith('no-') or '=' in name:
        raise Exception(f"not a warning name: {name!r}")  # not usable after -W or -Werror=
    return name


class CCompilerGcc(dlb_contrib_c.CCompiler):

    BINARY = 'gcc'  # helper file, looked-up in the context

    DIALECT = 'c99'  # https://gcc.gnu.org/onlinedocs/gcc/C-Dialect-Options.html#C-Dialect-Options

    SUPPRESSED_WARNINGS = ()  # names of warnings to be suppressed (e.g. 'unused-value')
    FATAL_WARNINGS = ('all',)  # names of warnings that should make the the compilation unsuccessful

    def get_compile_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return []

    async def redo(self, result, context):
        make_rules_file = context.create_temporary()
        object_file = context.create_temporary()

        try:
            sf = result.source_file.as_string()
            if any(c in sf for c in ':;\n\r'):
                raise Exception(f"limitation of 'gcc -MMD' does not allow this file name: {sf!r}")

            compile_arguments = [c for c in self.get_compile_arguments()]

            # https://gcc.gnu.org/onlinedocs/gcc/Directory-Options.html#Directory-Options
            if self.include_search_directories:
                for p in self.include_search_directories:
                    # note: '=' or '$SYSROOT' would be expanded by GCC
                    # str(p.native) never starts with these
                    compile_arguments.extend(['-I', p])  # looked up for #include <p> and #include "p"

            # https://gcc.gnu.org/onlinedocs/gcc/Warning-Options.html
            compile_arguments += ['-Wall']
            compile_arguments += ['-Wno-' + check_warning_name(n) for n in self.SUPPRESSED_WARNINGS]
            compile_arguments += ['-Werror=' + check_warning_name(n) for n in self.FATAL_WARNINGS]

            for macro, replacement in self.DEFINITIONS.items():
                if not dlb_contrib_c.IDENTIFIER.match(macro) and not dlb_contrib_c.FUNCTIONLIKE_MACRO.match(macro):
                    raise Exception(f"not a macro: {macro!r}")
                # *macro* is a string that does not start with '-' and does not contain '='
                if replacement is None:
                    compile_arguments += ['-U', macro]
                else:
                    replacement = str(replacement).strip()
                    if replacement == '1':
                        compile_arguments += ['-D', macro]
                    else:
                        compile_arguments += ['-D', f'{macro}={replacement}']

            # compile
            await context.execute_helper(
                self.BINARY,
                compile_arguments + [
                    '-x', 'c', '-std=' + self.DIALECT, '-c', '-o', object_file,
                    '-MMD', '-MT', '_ ', '-MF', make_rules_file,
                    result.source_file
                ]
            )

            # parse content of make_rules_file as a Makefile and add all paths in managed tree to included_files
            included_files = []
            with open(make_rules_file.native, 'r', encoding='utf-8') as dep_file:
                for p in dlb_contrib_make.additional_sources_from_rule(dep_file.readlines()):
                    try:
                        included_files.append(context.managed_tree_path_of(p))
                    except ValueError:
                        pass

            result.compiler_executable = context.helper[self.BINARY]
            result.included_files = included_files
            context.replace_output(result.object_file, object_file)
        except:
            os.remove(object_file.native)
            raise
        finally:
            os.remove(make_rules_file.native)
