# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.sh
import dlb_contrib.gcc
import sys
import os.path
import textwrap
import unittest
from typing import Iterable, Union


class CCompiler(dlb_contrib.gcc.CCompilerGcc):
    DEFINITIONS = {
        '__GNUC__': None,  # predefined
        'ONE': 1,
        'LINE_SEPARATOR': '"\\n"',
        'print(l)': 'printf(l LINE_SEPARATOR)'
    }
    DIALECT = 'c11'


class PathTest(unittest.TestCase):
    def test_fails_for_invalid_source_file(self):
        with self.assertRaises(ValueError):
            dlb_contrib.gcc.ObjectOrArchivePath('a:b.src')

    def test_fails_for_invalid_linkable_file(self):
        with self.assertRaises(ValueError):
            dlb_contrib.gcc.ObjectOrArchivePath('')
        with self.assertRaises(ValueError):
            dlb_contrib.gcc.ObjectOrArchivePath('.o')
        with self.assertRaises(ValueError):
            dlb_contrib.gcc.ObjectOrArchivePath('.a')
        with self.assertRaises(ValueError):
            dlb_contrib.gcc.ObjectOrArchivePath('..o')
        with self.assertRaises(ValueError):
            dlb_contrib.gcc.ObjectOrArchivePath('..a')


@unittest.skipIf(not os.path.isfile('/usr/bin/gcc'), 'requires gcc')
class CTest(testenv.TemporaryWorkingDirectoryTestCase):

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

        dlb.di.set_threshold_level(dlb.di.DEBUG)
        dlb.di.set_output_file(sys.stderr)

        t = CCompiler(source_files=['a.c'], object_files=['a.o'], include_search_directories=['i/'])
        with dlb.ex.Context():
            result = t.run()

        self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
        self.assertTrue(os.path.isfile(result.object_files[0].native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        with dlb.ex.Context():
            t.run()
            self.assertFalse(t.run())

        with dlb.ex.Context():
            dlb_contrib.gcc.CLinkerGcc(object_and_archive_files=['a.o'], linked_file='a').run()

    def test_fails_for_colon_in_name(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            CCompiler(source_files=['a:c'], object_files=['a.o'])
        msg = (
            "keyword argument for dependency role 'source_files' is invalid: ['a:c']\n"
            "  | reason: invalid path for 'Path': 'a:c' (must not contain these characters: '\\n','\\r',':',';')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_different_number_of_inputs_and_output(self):
        open('a.c', 'w').close()

        t = CCompiler(source_files=['a.c'], object_files=['a.o', 'b.o'])
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = "'object_files' must be of same length as 'source_files'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_multiple_inputs(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            def get_compile_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['a.c']

        t = C(source_files=['a.c'], object_files=['a.o'])
        with self.assertRaises(dlb.ex.HelperExecutionError):
            with dlb.ex.Context():
                t.run()

    def test_fails_for_invalid_warning(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            SUPPRESSED_WARNINGS = ('no-all',)

        t = C(source_files=['a.c'], object_files=['a.o'])
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                t.run()
        self.assertEqual("not a warning name: 'no-all'", str(cm.exception))

    def test_fails_for_invalid_macro(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            DEFINITIONS = {'a(': None}

        t = C(source_files=['a.c'], object_files=['a.o'])
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                t.run()
        self.assertEqual("not a macro: 'a('", str(cm.exception))


@unittest.skipIf(not os.path.isfile('/usr/bin/g++'), 'requires g++')
class CplusplusTest(testenv.TemporaryWorkingDirectoryTestCase):

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

        dlb.di.set_threshold_level(dlb.di.DEBUG)
        dlb.di.set_output_file(sys.stderr)

        t = dlb_contrib.gcc.CplusplusCompilerGcc(
            source_files=['a.c'], object_files=['a.o'], include_search_directories=['i/'])
        with dlb.ex.Context():
            result = t.run()

        self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
        self.assertTrue(os.path.isfile(result.object_files[0].native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        with dlb.ex.Context():
            t.run()
            self.assertFalse(t.run())

        with dlb.ex.Context():
            dlb_contrib.gcc.CplusplusLinkerGcc(object_and_archive_files=['a.o'], linked_file='a').run()


@unittest.skipIf(not os.path.isfile('/usr/bin/gcc'), 'requires gcc')
class CLinkerTest(testenv.TemporaryWorkingDirectoryTestCase):

    # noinspection PyPep8Naming
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
            dlb_contrib.gcc.CplusplusCompilerGcc(source_files=['a.c', 'b.c'], object_files=['a.o', 'b.o']).run()
            dlb_contrib.gcc.CplusplusCompilerGcc(source_files=['c.c'], object_files=['c.o']).run()

    def test_fails_without_proper_suffix(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            dlb_contrib.gcc.CLinkerGcc(object_and_archive_files=['o'], linked_file='e')
        msg = (
            "keyword argument for dependency role 'object_and_archive_files' is invalid: ['o']\n"
            "  | reason: invalid path for 'ObjectOrArchivePath': 'o' (must end with '.o' or '.a')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_succeeds_for_absolute_subprogram_directory(self):
        with dlb.ex.Context():
            dlb_contrib.gcc.CLinkerGcc(object_and_archive_files=['a.o', 'b.o', 'c.o'], linked_file='a',
                                       subprogram_directory='/usr/bin/').run()

    def test_succeeds_for_relative_subprogram_directory(self):
        try:
            os.symlink('/usr/', 'u', target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            dlb_contrib.gcc.CLinkerGcc(object_and_archive_files=['a.o', 'b.o', 'c.o'], linked_file='a',
                                       subprogram_directory='u/bin/').run()

    def test_finds_shared_library(self):
        class CSharedLibraryLinkerGcc(dlb_contrib.gcc.CLinkerGcc):
            def get_link_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['-shared']

        class CLinkerGcc(dlb_contrib.gcc.CLinkerGcc):
            LIBRARY_FILENAMES = ('libbc.so',)

        with dlb.ex.Context():
            CSharedLibraryLinkerGcc(object_and_archive_files=['b.o', 'c.o'], linked_file='lib/libbc.so').run()

        with dlb.ex.Context():
            CLinkerGcc(object_and_archive_files=['a.o'], library_search_directories=['lib/'],
                       linked_file='e').run()
