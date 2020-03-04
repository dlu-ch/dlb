# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Support of the language C by the GNU Compiler Collection."""

import sys
from typing import Iterable, Union
import os
import asyncio
import dlb.fs
import dlb_contrib_make
import dlb_contrib_c
assert sys.version_info >= (3, 7)


def check_warning_name(n: str) -> str:
    n = str(n)
    if not n or n.startswith('no-') or '=' in n:
        raise Exception(f"not a warning name: {n!r}")  # not usable after -W or -Werror=
    return n


class CCompilerGcc(dlb_contrib_c.CCompiler):

    BINARY = 'gcc'  # helper file, looked-up in the context

    DIALECT = 'c99'  # https://gcc.gnu.org/onlinedocs/gcc/C-Dialect-Options.html#C-Dialect-Options

    SUPPRESSED_WARNINGS = ()  # names of warnings to be suppressed (e.g. 'unused-value')
    FATAL_WARNINGS = ('all',)  # names of warnings that should make the the compilation unsuccessful

    def get_compile_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return []

    async def redo(self, result, context):
        make_rules_file = context.create_temporary(is_dir=False)
        object_file = context.create_temporary(is_dir=False)
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

            commandline_arguments = compile_arguments + [
                '-x', 'c', '-std=' + self.DIALECT, '-c', '-o', object_file,
                '-MMD', '-MT', '_ ', '-MF', make_rules_file,
                result.source_file
            ]

            commandline_tokens = [str(context.helper[self.BINARY].native)] + [
                str(n.native) if isinstance(n, dlb.fs.Path) else str(n)
                for n in commandline_arguments
            ]
            proc = await asyncio.create_subprocess_exec(*commandline_tokens, cwd=context.root_path.native)
            await proc.communicate()
            if proc.returncode != 0:
                raise Exception(f"compilation failed with exit code {proc.returncode}")

            # parse content of make_rules_file as a Makefile and add all paths in managed tree to included_files
            included_files = []
            with open(make_rules_file.native, 'r', encoding='utf-8') as dep_file:
                sources = dlb_contrib_make.sources_from_rules(dep_file.readlines())
            if len(sources) != 1:
                raise Exception(f"expect exactly one rule, got {len(sources)}")
            if len(sources[0]) < 1:
                raise Exception(f"expect at least one source in rule, got these: {sources[0]!r}")
            for p in sources[0][1:]:
                try:
                    included_files.append(context.managed_tree_path_of(p))
                except ValueError:
                    pass

            os.rename(object_file.native, result.object_file.native)
        except:
            os.remove(object_file.native)
            raise
        finally:
            os.remove(make_rules_file.native)

        result.included_files = included_files
