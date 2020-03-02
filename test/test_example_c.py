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
import pathlib
import textwrap
import asyncio
import unittest
import tools_for_test


@unittest.skipIf(not os.path.isfile('/usr/bin/gcc'), 'requires GCC')
class GccCompiler(dlb.ex.Tool):
    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

    async def redo(self, result, context):
        make_rules_file = context.create_temporary(is_dir=False)
        object_file = context.create_temporary(is_dir=False)
        try:
            sf = result.source_file.as_string()
            if any(c in sf for c in ':;\n\r'):
                raise Exception(f"limitation of gcc -MMD does not allow this file name: {sf!r}")

            proc = await asyncio.create_subprocess_exec(
                '/usr/bin/gcc',
                '-O2', '-g', '-Wall',
                '-x', 'c', '-c', '-o', str(object_file.native),
                '-MMD', '-MT', '_ ', '-MF', str(make_rules_file.native),
                str(result.source_file.native))

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

        pathlib.Path('.dlbroot').mkdir()

        with pathlib.Path('a.c').open('w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                #include "a.h"

                int main() {
                    printf("tschou tzaeme\\n");
                    return 0;
                }
                '''
            ))

        with pathlib.Path('a.h').open('w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                # include <stdio.h>
                '''
            ))

        dlb.di.set_output_file(sys.stderr)

    def test_compile(self):
        with dlb.ex.Context():
            result = GccCompiler(source_file='a.c', object_file='a.o').run()

        print(result.included_files)
        self.assertTrue(os.path.isfile(result.object_file.native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        with dlb.ex.Context():
            GccCompiler(source_file='a.c', object_file='a.o').run()

        with dlb.ex.Context():
            self.assertIsNone(GccCompiler(source_file='a.c', object_file='a.o').run())
