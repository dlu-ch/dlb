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
import dlb_contrib_c_gcc
import textwrap
import unittest
from typing import Iterable, Union
import tools_for_test


class CCompiler(dlb_contrib_c_gcc.CCompilerGcc):
    DIALECT = 'c11'


@unittest.skipIf(not os.path.isfile('/usr/bin/gcc'), 'requires GCC')
class GccTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_example(self):
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

        t = CCompiler(source_file='a.c', object_file='a.o', include_search_directories=['i/'])
        with dlb.ex.Context(find_helpers=True):
            result = t.run()

        self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
        self.assertTrue(os.path.isfile(result.object_file.native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        self.assertTrue(result.compiler_executable.is_absolute())
        self.assertTrue(os.path.isfile(result.compiler_executable.native))

        with dlb.ex.Context(find_helpers=True):
            t.run()
            self.assertIsNone(t.run())

    def test_fails_for_colon_in_name(self):
        with open('./a:c', 'w'):
            pass

        t = CCompiler(source_file='a:c', object_file='a.o')
        with self.assertRaises(Exception) as cm:
            with dlb.ex.Context(find_helpers=True):
                t.run()
        self.assertEqual("limitation of 'gcc -MMD' does not allow this file name: 'a:c'", str(cm.exception))

    def test_fails_for_multiple_inputs(self):
        with open('a.c', 'w'):
            pass

        class C(CCompiler):
            def get_compile_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['a.c']

        t = C(source_file='a.c', object_file='a.o')
        with self.assertRaises(Exception):
            with dlb.ex.Context(find_helpers=True):
                t.run()

    def test_fails_for_invalid_warning(self):
        with open('a.c', 'w'):
            pass

        class C(CCompiler):
            SUPPRESSED_WARNINGS = ('no-all',)

        t = C(source_file='a.c', object_file='a.o')
        with self.assertRaises(Exception) as cm:
            with dlb.ex.Context(find_helpers=True):
                t.run()
        self.assertEqual("not a warning name: 'no-all'", str(cm.exception))
