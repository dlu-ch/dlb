# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.sh
import dlb_contrib.gcc
import sys
import os.path
import shutil
import textwrap
import unittest
from typing import List, Iterable, Union


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


@unittest.skipIf(not shutil.which('gcc'), 'requires gcc in $PATH')
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
            result = t.start()

        self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
        self.assertTrue(os.path.isfile(result.object_files[0].native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        with dlb.ex.Context():
            t.start()
            self.assertFalse(t.start())

        with dlb.ex.Context():
            dlb_contrib.gcc.CLinkerGcc(object_and_archive_files=['a.o'], linked_file='a').start()

    def test_fails_for_colon_in_name(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            CCompiler(source_files=['a:c'], object_files=['a.o'])
        msg = (
            "keyword argument for dependency role 'source_files' is invalid: ['a:c']\n"
            "  | reason: invalid path for 'Path': 'a:c' (must not contain these characters: '\\n','\\r',':',';')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_more_outputs_than_inputs(self):
        open('a.c', 'w').close()

        t = CCompiler(source_files=['a.c'], object_files=['a.o', 'b.o'])
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                t.start()
        msg = "'object_files' must be of at most the same length as 'source_files'"
        self.assertEqual(msg, str(cm.exception))

    def test_succeeds_for_less_outputs_than_inputs(self):
        open('a.c', 'w').close()

        t = CCompiler(source_files=['a.c'], object_files=[])
        with dlb.ex.Context():
            t.start()

    def test_fails_for_multiple_inputs(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            def get_extra_compile_arguments(self) -> List[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['a.c']

        t = C(source_files=['a.c'], object_files=['a.o'])
        with self.assertRaises(dlb.ex.HelperExecutionError):
            with dlb.ex.Context():
                t.start()

    def test_fails_for_invalid_warning(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            SUPPRESSED_WARNINGS = ('no-all',)

        t = C(source_files=['a.c'], object_files=['a.o'])
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                t.start()
        self.assertEqual("not a warning name: 'no-all'", str(cm.exception))

    def test_fails_for_invalid_macro(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            DEFINITIONS = {'a(': None}

        t = C(source_files=['a.c'], object_files=['a.o'])
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                t.start()
        self.assertEqual("not a macro: 'a('", str(cm.exception))


@unittest.skipIf(not shutil.which('g++'), 'requires g++ in $PATH')
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
            result = t.start()

        self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
        self.assertTrue(os.path.isfile(result.object_files[0].native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

        with dlb.ex.Context():
            t.start()
            self.assertFalse(t.start())

        with dlb.ex.Context():
            dlb_contrib.gcc.CplusplusLinkerGcc(object_and_archive_files=['a.o'], linked_file='a').start()


@unittest.skipIf(not shutil.which('gcc'), 'requires gcc in $PATH')
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
            dlb_contrib.gcc.CplusplusCompilerGcc(source_files=['a.c', 'b.c'], object_files=['a.o', 'b.o']).start()
            dlb_contrib.gcc.CplusplusCompilerGcc(source_files=['c.c'], object_files=['c.o']).start()

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
                                       subprogram_directory='/usr/bin/').start()

    def test_succeeds_for_relative_subprogram_directory(self):
        try:
            os.symlink('/usr/', 'u', target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            dlb_contrib.gcc.CLinkerGcc(object_and_archive_files=['a.o', 'b.o', 'c.o'], linked_file='a',
                                       subprogram_directory='u/bin/').start()

    def test_finds_shared_library(self):
        class CSharedLibraryLinkerGcc(dlb_contrib.gcc.CLinkerGcc):
            def get_extra_link_arguments(self) -> List[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['-shared']

        class CLinkerGcc(dlb_contrib.gcc.CLinkerGcc):
            LIBRARY_FILENAMES = ('libbc.so',)

        with dlb.ex.Context():
            CSharedLibraryLinkerGcc(object_and_archive_files=['b.o', 'c.o'], linked_file='lib/libbc.so').start()

        with dlb.ex.Context():
            CLinkerGcc(object_and_archive_files=['a.o'], library_search_directories=['lib/'],
                       linked_file='e').start()


@unittest.skipIf(not shutil.which('gcc'), 'requires gcc in $PATH')
class VersionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_version_is_string_with_dot(self):
        # noinspection PyPep8Naming
        Tools = [
            dlb_contrib.gcc.CCompilerGcc,
            dlb_contrib.gcc.CplusplusCompilerGcc,
            dlb_contrib.gcc.CLinkerGcc,
            dlb_contrib.gcc.CplusplusLinkerGcc
        ]

        class QueryVersion(dlb_contrib.generic.VersionQuery):
            VERSION_PARAMETERS_BY_EXECUTABLE = {
                Tool.EXECUTABLE: Tool.VERSION_PARAMETERS
                for Tool in Tools
            }

        with dlb.ex.Context():
            version_by_path = QueryVersion().start().version_by_path
            self.assertEqual(len(QueryVersion.VERSION_PARAMETERS_BY_EXECUTABLE), len(version_by_path))
            for Tool in Tools:
                path = dlb.ex.Context.active.helper[Tool.EXECUTABLE]
                version = version_by_path[path]
                self.assertIsInstance(version, str)
                self.assertGreaterEqual(version.count('.'), 2)


@unittest.skipIf(not shutil.which('gcc'), 'requires gcc in $PATH')
class CCompileCheckTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_not_overwritten(self):
        import dlb_contrib.clike
        self.assertIs(dlb_contrib.clike.ClikeCompiler.does_source_compile.__func__,
                      dlb_contrib.gcc.CCompilerGcc.does_source_compile.__func__)

    def test_empty_does_compile(self):
        with dlb.ex.Context():
            self.assertTrue(dlb_contrib.gcc.CCompilerGcc.does_source_compile(''))

    def test_existing_include_does_compile(self):
        with dlb.ex.Context():
            self.assertTrue(dlb_contrib.gcc.CCompilerGcc.does_source_compile('#include <stdint.h>'))
            self.assertFalse(dlb_contrib.gcc.CCompilerGcc.does_source_compile('#include "does/not/exist"'))

    def test_error_does_not_compile(self):
        with dlb.ex.Context():
            self.assertFalse(dlb_contrib.gcc.CCompilerGcc.does_source_compile('#error'))

    def test_does_no_output_messages(self):
        import io
        output = io.StringIO()
        dlb.di.set_output_file(output)
        with dlb.ex.Context():
            dlb_contrib.gcc.CCompilerGcc.does_source_compile('')
            dlb_contrib.gcc.CCompilerGcc.does_source_compile('#error')
        self.assertEqual('', output.getvalue())


@unittest.skipIf(not shutil.which('gcc'), 'requires gcc in $PATH')
class CConstantConditionCheckTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_not_overwritten(self):
        import dlb_contrib.clike
        self.assertIs(dlb_contrib.clike.ClikeCompiler.check_constant_expression.__func__,
                      dlb_contrib.gcc.CCompilerGcc.check_constant_expression.__func__)

    def test_valid_condition_is_not_none(self):
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression('1 < 2')
            self.assertIsNotNone(r)
            self.assertTrue(r)

            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression('1 > 2')
            self.assertIsNotNone(r)
            self.assertFalse(r)

    def test_invalid_condition_is_none(self):
        with dlb.ex.Context():
            self.assertIsNone(dlb_contrib.gcc.CCompilerGcc.check_constant_expression('1 <'))

    def test_condition_can_use_preamble(self):
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression('UINT_LEAST8_MAX <= UINT_LEAST16_MAX',
                                                                       preamble='#include <stdint.h>')
            self.assertTrue(r)

    def test_valid_condition_with_invalid_preamble_is_none(self):
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression('UINT_LEAST8_MAX <= UINT_LEAST16_MAX',
                                                                       preamble='#include')
            self.assertIsNone(r)

    def test_white_space_condition_is_none(self):
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression('', check_syntax=False)
            self.assertIsNone(r)
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression('\r   \n\t', check_syntax=False)
            self.assertIsNone(r)

    def test_without_check_is_none(self):
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression('1', by_compiler=False, by_preprocessor=False,
                                                                       check_syntax=False)
            self.assertIsNone(r)

    def test_sizeof_is_none_for_preprocessor(self):
        expr = 'sizeof(char) == 1'
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression(expr, by_compiler=False, by_preprocessor=True)
            self.assertIsNone(r)
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression(expr,  by_compiler=True, by_preprocessor=False)
            self.assertTrue(r)
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression(expr, by_compiler=True, by_preprocessor=True)
            self.assertIsNone(r)

    def test_undefined_is_none_for_compiler(self):
        expr = 'xy == 0'
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression(expr, by_compiler=False, by_preprocessor=True)
            self.assertTrue(r)
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression(expr, by_compiler=True, by_preprocessor=False)

            self.assertIsNone(r)
            r = dlb_contrib.gcc.CCompilerGcc.check_constant_expression(expr, by_compiler=True, by_preprocessor=True)
            self.assertIsNone(r)


@unittest.skipIf(not shutil.which('gcc'), 'requires gcc in $PATH')
class CSizeOfCheckTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_not_overwritten(self):
        import dlb_contrib.clike
        self.assertIs(dlb_contrib.clike.ClikeCompiler.get_size_of.__func__,
                      dlb_contrib.gcc.CCompilerGcc.get_size_of.__func__)

    def test_char_is_one(self):
        with dlb.ex.Context():
            self.assertEqual(1, dlb_contrib.gcc.CCompilerGcc.get_size_of('char'))

    def test_uint16_is_at_least_two(self):
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.get_size_of('uint_least16_t', preamble='#include <stdint.h>')
            self.assertLessEqual(2, r)

    def test_chararray_is_count(self):
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.get_size_of('char[9999]', preamble='#include <stdint.h>')
            self.assertEqual(9999, r)
            r = dlb_contrib.gcc.CCompilerGcc.get_size_of('char[10000]', preamble='#include <stdint.h>')
            self.assertEqual(10000, r)
            r = dlb_contrib.gcc.CCompilerGcc.get_size_of('char[10001]', preamble='#include <stdint.h>')
            self.assertEqual(10001, r)

    def test_invalid_is_none(self):
        with dlb.ex.Context():
            r = dlb_contrib.gcc.CCompilerGcc.get_size_of(')', preamble='#include <stdint.h>')
            self.assertIsNone(r)

            r = dlb_contrib.gcc.CCompilerGcc.get_size_of('xyz')
            self.assertIsNone(r)

            r = dlb_contrib.gcc.CCompilerGcc.get_size_of('int', preamble='#error')
            self.assertIsNone(r)
