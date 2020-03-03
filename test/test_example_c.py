# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib_lang_make
import os
import textwrap
import asyncio
import unittest
from typing import Iterable, Union
import tools_for_test


# noinspection PyAbstractClass
class CCompiler(dlb.ex.Tool):

    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()

    # tuple of paths of directories that are to be searched for include files in addition to the system include files
    include_search_directories = dlb.ex.Tool.Input.Directory[:](required=False)

    # paths of all files in the managed tree directly or indirectly included by *source_file*
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)


@unittest.skipIf(not os.path.isfile('/usr/bin/gcc'), 'requires GCC')
class CCompilerGcc(CCompiler):

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
                raise Exception(f"limitation of gcc -MMD does not allow this file name: {sf!r}")

            def check_warning_name(n):
                n = str(n)
                if not n or n.startswith('no-') or '=' in n:
                    raise Exception(f"not a warning name: {n}")
                return n

            compile_arguments = [c for c in self.get_compile_arguments()]

            # https://gcc.gnu.org/onlinedocs/gcc/Directory-Options.html#Directory-Options
            if self.include_search_directories:
                for p in self.include_search_directories:
                    # note: '=' or '$SYSROOT' would be expanded by GCC
                    # str(p.native) never starts with these
                    compile_arguments.extend(['-I', p])  # looked up for #include <p> and #include "p"

            # https://gcc.gnu.org/onlinedocs/gcc/Warning-Options.html
            compile_arguments.append('-Wall')
            compile_arguments.extend(['-Wno-' + check_warning_name(n) for n in self.SUPPRESSED_WARNINGS])
            compile_arguments.extend(['-Werror=' + check_warning_name(n) for n in self.FATAL_WARNINGS])

            commandline_arguments = compile_arguments + [
                '-x', 'c', '-std=' + self.DIALECT, '-c', '-o', object_file,
                '-MMD', '-MT', '_ ', '-MF', make_rules_file,
                result.source_file
            ]

            commandline_tokens = ['/usr/bin/gcc']
            for n in commandline_arguments:
                if isinstance(n, dlb.fs.Path):
                    n = n.native
                commandline_tokens.append(str(n))
            proc = await asyncio.create_subprocess_exec(*commandline_tokens, cwd=context.root_path.native)
            await proc.communicate()
            if proc.returncode != 0:
                raise Exception(f"compilation failed with exit code {proc.returncode}")

            # parse content of make_rules_file as a Makefile and add all paths in managed tree to included_files
            included_files = []
            with open(make_rules_file.native, 'r', encoding='utf-8') as dep_file:
                sources = dlb_contrib_lang_make.sources_from_rules(dep_file.readlines())
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


class GccTest(tools_for_test.TemporaryDirectoryTestCase):

    def setUp(self):
        super().setUp()

        os.mkdir('.dlbroot')
        os.mkdir('i')

        with open('a.c', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                #include "a.h"

                int main() {
                    printf(GREETING "\\n");
                    return 0;
                }
                '''
            ))

        with open('a.h', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                #include <stdio.h>
                  # include "a greeting.inc"
                '''
            ))

        with open(os.path.join('i', 'a greeting.inc'), 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                #define GREETING "tschou tzaeme"
                '''
            ))

        dlb.di.set_output_file(sys.stderr)

    def test_compile(self):
        t = CCompilerGcc(source_file='a.c', object_file='a.o', include_search_directories=['i/'])
        with dlb.ex.Context():
            result = t.run()

        self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
        self.assertTrue(os.path.isfile(result.object_file.native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        with dlb.ex.Context():
            t.run()
            self.assertIsNone(t.run())
