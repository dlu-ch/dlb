# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.msvc
import sys
import os.path
import textwrap
import unittest
from typing import List, Union


# VCTOOLSINSTALLDIR - see <program-dir>\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars*.bat
vctools_install_dir = 'C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\' \
                      'VC\\Tools\\MSVC\\14.25.28610\\'


class CCompiler(dlb_contrib.msvc.CCompilerMsvc):
    DEFINITIONS = {
        'ONE': 1,
        'LINE_SEPARATOR': '"\\n"'
    }


class DllLinker(dlb_contrib.msvc.LinkerMsvc):
    def get_extra_link_arguments(self) -> List[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return [
            '/NODEFAULTLIB',
            '/NOENTRY',
            '/DLL',
        ]


class ThisIsAUnitTest(unittest.TestCase):
    pass


class NonWindowsTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_toolinstance_can_be_constructed(self):
        dlb_contrib.msvc.CCompilerMsvc(source_files=['a.c'], object_files=['a.o'], include_search_directories=['i/'])
        dlb_contrib.msvc.CplusplusCompilerMsvc(source_files=['a.c'], object_files=['a.o'],
                                               include_search_directories=['i/'])
        dlb_contrib.msvc.LinkerMsvc(linkable_files=['a.o'], linked_file='a')

    @unittest.skipUnless(sys.platform != 'win32', 'requires non-Windows platform')
    def test_fails_on_run(self):
        os.mkdir('i')
        open('a.c', 'x').close()
        open('a.o', 'x').close()

        with self.assertRaises(RuntimeError), dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
            dlb.ex.Context.active.env['SYSTEMROOT'] = 'a'
            dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*', example='C:\\X;D:\\Y')
            dlb.ex.Context.active.env['INCLUDE'] = 'a'
            CCompiler(source_files=['a.c'], object_files=['a.o'], include_search_directories=['i/']).start()


@unittest.skipUnless(os.path.isdir(vctools_install_dir), 'requires msvc')
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

                int main() {
                    const char *p = GREETING;
                    return 0;
                }
                '''
            ))

        with open('a.h', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
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
        binary_path = dlb.fs.Path(dlb.fs.Path.Native(vctools_install_dir), is_dir=True) / 'bin/Hostx64/x64/'

        t = CCompiler(source_files=['a.c'], object_files=['a.o'], include_search_directories=['i/'])
        with dlb.ex.Context():
            # see <program-dir>\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars*.bat
            dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
            dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
            dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*', example='C:\\X;D:\\Y')
            dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
            dlb.ex.Context.active.helper['cl.exe'] = binary_path / 'cl.exe'

            with dlb.ex.Context():
                result = t.start()

            self.assertEqual((dlb.fs.Path('a.h'), dlb.fs.Path('i/a greeting.inc')), result.included_files)
            self.assertTrue(os.path.isfile(result.object_files[0].native))
            self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

            with dlb.ex.Context():
                t.start()
                self.assertFalse(t.start())

        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
            dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
            dlb.ex.Context.active.env.import_from_outer('LIB', pattern=r'[^;]+(;[^;]+)*', example='C:\\X;D:\\Y')
            dlb.ex.Context.active.env['LIB'] = os.getcwd()
            dlb.ex.Context.active.helper['link.exe'] = binary_path / 'link.exe'
            DllLinker(linkable_files=['a.o'], linked_file='a').start()

    def test_can_undefine_predefined(self):
        # Note: Do not combine undefining predefined preprocessor macros with inclusion of file of the
        # standard library.

        with open('a.c', 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(
                '''
                #ifdef _MSC_VER
                    #error "_MSC_VER is defined"
                #endif

                int main() {
                    return 0;
                }
                '''
            ))

        dlb.di.set_threshold_level(dlb.di.DEBUG)
        dlb.di.set_output_file(sys.stderr)
        binary_path = dlb.fs.Path(dlb.fs.Path.Native(vctools_install_dir), is_dir=True) / 'bin/Hostx64/x64/'

        t = dlb_contrib.msvc.CCompilerMsvc(source_files=['a.c'], object_files=['a.o'],
                                           DEFINITIONS={'_MSC_VER': None})  # predefined
        with dlb.ex.Context():
            # see <program-dir>\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars*.bat
            dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
            dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
            dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*', example='C:\\X;D:\\Y')
            dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
            dlb.ex.Context.active.helper['cl.exe'] = binary_path / 'cl.exe'

            result = t.start()

        self.assertEqual((), result.included_files)
        self.assertTrue(os.path.isfile(result.object_files[0].native))
        self.assertTrue(all(os.path.isfile(p.native) for p in result.included_files))

    def test_detects_included_files_with_unrepresentable_character_in_abspath(self):
        strange_dir_name = '统一码'  # not in cp437 or cp850

        os.mkdir(strange_dir_name)
        with testenv.DirectoryChanger(strange_dir_name):
            os.mkdir('.dlbroot')

            open('a.h', 'xb').close()
            with open('a.c', 'xb') as f:
                f.write(b'#include "a.h"\n')

            dlb.di.set_threshold_level(dlb.di.INFO)
            dlb.di.set_output_file(sys.stderr)
            binary_path = dlb.fs.Path(dlb.fs.Path.Native(vctools_install_dir), is_dir=True) / 'bin/Hostx64/x64/'

            t = CCompiler(source_files=['a.c'], object_files=['a.o'])
            with dlb.ex.Context():
                # see <program-dir>\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars*.bat
                dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
                dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
                dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*',
                                                            example='C:\\X;D:\\Y')
                dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
                dlb.ex.Context.active.helper['cl.exe'] = binary_path / 'cl.exe'
                result = t.start()
                self.assertEqual((dlb.fs.Path('a.h'),), result.included_files)

    def test_fails_for_included_files_with_unrepresentable_character_in_workingtreepath(self):
        strange_dir_name = '统一码'  # # not in cp437 or cp850

        os.mkdir(strange_dir_name)
        open(os.path.join(strange_dir_name, 'a.h'), 'xb').close()

        with open('a.c', 'xb') as f:
            f.write(b'#include "a.h"\n')

        dlb.di.set_threshold_level(dlb.di.INFO)
        dlb.di.set_output_file(sys.stderr)
        binary_path = dlb.fs.Path(dlb.fs.Path.Native(vctools_install_dir), is_dir=True) / 'bin/Hostx64/x64/'

        t = CCompiler(source_files=['a.c'], object_files=['a.o'], include_search_directories=[strange_dir_name + '/'])
        with self.assertRaises(FileNotFoundError) as cm:
            with dlb.ex.Context():
                # see <program-dir>\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars*.bat
                dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
                dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
                dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*',
                                                            example='C:\\X;D:\\Y')
                dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
                dlb.ex.Context.active.helper['cl.exe'] = binary_path / 'cl.exe'
                t.start()
        regex = (
            r"(?m)\A"
            r"reportedly included file not found: '\?\?\?/a\.h'\n"
            r"  \| ambiguity in the ANSI encoding \('cp[0-9]+'\) of its path\?\Z"
        )
        self.assertRegex(str(cm.exception), regex)
        self.assertTrue(os.path.isfile('a.o'))

    def test_fails_for_more_outputs_than_inputs(self):
        open('a.c', 'w').close()

        t = CCompiler(source_files=['a.c'], object_files=['a.o', 'b.o'])
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
                dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
                dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*',
                                                            example='C:\\X;D:\\Y')
                dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
                t.start()
        msg = "'object_files' must be of at most the same length as 'source_files'"
        self.assertEqual(msg, str(cm.exception))

    def test_succeeds_for_less_outputs_than_inputs(self):
        open('a.c', 'w').close()

        binary_path = dlb.fs.Path(dlb.fs.Path.Native(vctools_install_dir), is_dir=True) / 'bin/Hostx64/x64/'

        t = CCompiler(source_files=['a.c'], object_files=[])
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
            dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
            dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*',
                                                        example='C:\\X;D:\\Y')
            dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
            dlb.ex.Context.active.helper['cl.exe'] = binary_path / 'cl.exe'
            t.start()

    def test_fails_for_invalid_macro(self):
        open('a.c', 'w').close()

        class C(CCompiler):
            DEFINITIONS = {'min(a, b)': None}

        t = C(source_files=['a.c'], object_files=['a.o'])
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
                dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
                dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*',
                                                            example='C:\\X;D:\\Y')
                dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
                t.start()
        self.assertEqual("not an object-like macro: 'min(a, b)'", str(cm.exception))

    def test_fails_for_argument_with_at(self):
        class Linker(dlb_contrib.msvc.LinkerMsvc):
            def get_extra_link_arguments(self) -> List[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['/DLL', '@x']

        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                open('a.o', 'xb').close()
                dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
                dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
                dlb.ex.Context.active.env.import_from_outer('LIB', pattern=r'[^;]+(;[^;]+)*', example='C:\\X;D:\\Y')
                dlb.ex.Context.active.env['LIB'] = os.getcwd()
                Linker(linkable_files=['a.o'], linked_file='a').start()
        self.assertEqual("argument must not start with '@': '@x'", str(cm.exception))

    def test_ignores_extension(self):
        with open('a.cpp', 'wb') as f:
            f.write(
                b'#ifdef __cplusplus\n'
                b'#error is C++ compiler\n'
                b'#endif\n'
            )

        binary_path = dlb.fs.Path(dlb.fs.Path.Native(vctools_install_dir), is_dir=True) / 'bin/Hostx64/x64/'

        t = dlb_contrib.msvc.CCompilerMsvc(source_files=['a.cpp'], object_files=['a.o'])
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
            dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
            dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*',
                                                        example='C:\\X;D:\\Y')
            dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
            dlb.ex.Context.active.helper['cl.exe'] = binary_path / 'cl.exe'
            t.start()


@unittest.skipUnless(os.path.isdir(vctools_install_dir), 'requires msvc')
class CppTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_ignores_extension(self):
        with open('a.c', 'wb') as f:
            f.write(
                b'#ifndef __cplusplus\n'
                b'#error is C compiler\n'
                b'#endif\n'
            )

        binary_path = dlb.fs.Path(dlb.fs.Path.Native(vctools_install_dir), is_dir=True) / 'bin/Hostx64/x64/'

        t = dlb_contrib.msvc.CplusplusCompilerMsvc(source_files=['a.c'], object_files=['a.o'])
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
            dlb.ex.Context.active.env['SYSTEMROOT'] = os.environ['SYSTEMROOT']
            dlb.ex.Context.active.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*',
                                                        example='C:\\X;D:\\Y')
            dlb.ex.Context.active.env['INCLUDE'] = os.getcwd()
            dlb.ex.Context.active.helper['cl.exe'] = binary_path / 'cl.exe'
            t.start()
