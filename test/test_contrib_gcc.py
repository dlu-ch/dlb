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
import dlb_contrib_sh
import dlb_contrib_gcc
import textwrap
import unittest
from typing import Iterable, Union
import tools_for_test


class CCompiler(dlb_contrib_gcc.CCompilerGcc):
    DEFINITIONS = {
        '__GNUC__': None,  # predefined
        'ONE': 1,
        'LINE_SEPARATOR': '"\\n"',
        'print(l)': 'printf(l LINE_SEPARATOR)'
    }
    DIALECT = 'c11'


@unittest.skipIf(not os.path.isfile('/usr/bin/gcc'), 'requires gcc')
class CTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_example(self):
        os.mkdir('i')

        with open('a.c', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                #include "a.h"
                
                #ifndef ONE
                    #error "ONE is not defined"
                #endif
                
                #ifdef __GNUC__
                    #error "__GNUC__ is defined"
                #endif

                int main() {
                    print(GREETING);
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
        with dlb.ex.Context():
            result = t.run()

        self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
        self.assertTrue(os.path.isfile(result.object_file.native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        self.assertTrue(result.compiler_executable.is_absolute())
        self.assertTrue(os.path.isfile(result.compiler_executable.native))

        with dlb.ex.Context():
            t.run()
            self.assertFalse(t.run())

        with dlb.ex.Context():
            dlb_contrib_gcc.CLinkerGcc(object_and_archive_files=['a.o'], linked_file='a').run()

    def test_fails_for_colon_in_name(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            CCompiler(source_file='a:c', object_file='a.o')
        msg = (
            "keyword argument for dependency role 'source_file' is invalid: 'a:c'\n"
            "  | reason: invalid path for 'Path': 'a:c' (must not contain these characters: '\\n','\\r',':',';')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_multiple_inputs(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            def get_compile_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['a.c']

        t = C(source_file='a.c', object_file='a.o')
        with self.assertRaises(Exception):
            with dlb.ex.Context():
                t.run()

    def test_fails_for_invalid_warning(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            SUPPRESSED_WARNINGS = ('no-all',)

        t = C(source_file='a.c', object_file='a.o')
        with self.assertRaises(Exception) as cm:
            with dlb.ex.Context():
                t.run()
        self.assertEqual("not a warning name: 'no-all'", str(cm.exception))

    def test_fails_for_invalid_macro(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            DEFINITIONS = {'a(': None}

        t = C(source_file='a.c', object_file='a.o')
        with self.assertRaises(Exception) as cm:
            with dlb.ex.Context():
                t.run()
        self.assertEqual("not a macro: 'a('", str(cm.exception))


@unittest.skipIf(not os.path.isfile('/usr/bin/g++'), 'requires g++')
class CplusplusTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_example(self):
        os.mkdir('i')

        with open('a.c', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                #include "a.h"

                int main() {
                    std::cout << GREETING;
                    return 0;
                }
                '''
            ))

        with open('a.h', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                #include <iostream>
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

        t = dlb_contrib_gcc.CplusplusCompilerGcc(
            source_file='a.c', object_file='a.o', include_search_directories=['i/'])
        with dlb.ex.Context():
            result = t.run()

        self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
        self.assertTrue(os.path.isfile(result.object_file.native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        self.assertTrue(result.compiler_executable.is_absolute())
        self.assertTrue(os.path.isfile(result.compiler_executable.native))

        with dlb.ex.Context():
            t.run()
            self.assertFalse(t.run())

        with dlb.ex.Context():
            dlb_contrib_gcc.CplusplusLinkerGcc(object_and_archive_files=['a.o'], linked_file='a').run()


@unittest.skipIf(not os.path.isfile('/usr/bin/gcc'), 'requires gcc')
class CLinkerTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def setUp(self):
        super().setUp()

        with open('a.c', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                int f(int x);
                int g(int x);
                
                int main() {
                    return f(g(1));
                }
                '''
            ))

        with open('b.c', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                int f(int x) {
                    return x + 1;
                }
                '''
            ))

        with open('c.c', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                int g(int x) {
                    return 2 * x;
                }
                '''
            ))

        with dlb.ex.Context():
            dlb_contrib_gcc.CplusplusCompilerGcc(source_file='a.c', object_file='a.o').run()
            dlb_contrib_gcc.CplusplusCompilerGcc(source_file='b.c', object_file='b.o').run()
            dlb_contrib_gcc.CplusplusCompilerGcc(source_file='c.c', object_file='c.o').run()

    def test_fails_without_proper_suffix(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            dlb_contrib_gcc.CLinkerGcc(object_and_archive_files=['o'], linked_file='e')
        msg = (
            "keyword argument for dependency role 'object_and_archive_files' is invalid: ['o']\n"
            "  | reason: invalid path for 'ObjectOrArchivePath': 'o' (must end with '.o' or '.a')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_succeeds_for_absolute_subprogram_directory(self):
        with dlb.ex.Context():
            dlb_contrib_gcc.CLinkerGcc(object_and_archive_files=['a.o', 'b.o', 'c.o'], linked_file='a',
                                       subprogram_directory='/usr/bin/').run()

    def test_succeeds_for_relative_subprogram_directory(self):
        try:
            os.symlink('/usr/', 'u', target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            dlb_contrib_gcc.CLinkerGcc(object_and_archive_files=['a.o', 'b.o', 'c.o'], linked_file='a',
                                       subprogram_directory='u/bin/').run()

    def test_finds_shared_library(self):
        class CSharedLibraryLinkerGcc(dlb_contrib_gcc.CLinkerGcc):
            def get_link_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['-shared']

        class CLinkerGcc(dlb_contrib_gcc.CLinkerGcc):
            LIBRARY_FILENAMES = ('libbc.so',)

        class ShowGccVersion(dlb_contrib_sh.ShScriptlet):
            SCRIPTLET = 'gcc -v'

        with dlb.ex.Context():
            ShowGccVersion().run()
            CSharedLibraryLinkerGcc(object_and_archive_files=['b.o', 'c.o'], linked_file='lib/libbc.so').run()

        with dlb.ex.Context():
            CLinkerGcc(object_and_archive_files=['a.o'], library_search_directories=['lib/'],
                       linked_file='e').run()
