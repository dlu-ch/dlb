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
import marshal
import io
import unittest
import tools_for_test


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()
    log_file = dlb.ex.Tool.Output.RegularFile(required=False, explicit=False)
    include_directories = dlb.ex.Tool.Input.Directory[:](required=False)
    dummy_file = dlb.ex.Tool.Input.NonRegularFile(required=False)
    dummy_dir = dlb.ex.Tool.Output.Directory(required=False)

    async def redo(self, result, context):
        dlb.di.inform("redoing right now")
        open((context.root_path / self.object_file).native, 'wb').close()


class RunWithoutRedoTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    # noinspection PyAbstractClass
    def test_fails_without_redo(self):

        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()

        with self.assertRaises(NotImplementedError):
            with dlb.ex.Context():
                t = BTool(object_file='a.o')
                t.run()


class RunWithMissingExplicitInputDependencyTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_nonexistent_inputfile(self):
        regex = (
            r"\A()input dependency 'source_file' contains a path of a non-existent "
            r"filesystem object: 'src/a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.run()

        regex = (
            r"\A()input dependency 'source_file' contains a path of a non-existent "
            r"filesystem object: 'src/b/\.\./a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/b/../a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.run()

    def test_fails_for_nonnormalized_inputfile_path(self):
        regex = (
            r"(?m)\A"
            r"input dependency 'source_file' contains an invalid path: '\.\./a\.cpp'\n"
            r"  | reason: not in managed tree\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='../a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.run()


class RunWithAbsoluteExplicitInputDependencyTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_absolute_in_managed_tree_remains_absolute(self):
        os.mkdir('.dlbroot')
        open('a.cpp', 'xb').close()

        with dlb.ex.Context() as c:
            t = ATool(source_file=c.root_path / 'a.cpp', object_file='a.o')
            r = t.run()
            self.assertEqual(c.root_path / 'a.cpp', r.source_file)

    def test_absolute_can_be_outside_managed_tree(self):
        open('x.cpp', 'xb').close()

        os.mkdir('t')
        with tools_for_test.DirectoryChanger('t'):
            os.mkdir('.dlbroot')
            open('a.cpp', 'xb').close()

            with dlb.ex.Context() as c:
                t = ATool(source_file=c.root_path / '../x.cpp', object_file='a.o')
                t.run()


class RunWithExplicitOutputDependencyTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_nonnormalized_outputfile_path(self):
        open('a.cpp', 'xb').close()

        regex = (
            r"(?m)\A"
            r"output dependency 'object_file' contains a path that is not a managed tree path: '\.\./a\.o'\n"
            r"  | reason: is an upwards path: '\.\.[\\/]+a\.o'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='a.cpp', object_file='../a.o')
                t.run()


class RunWithMissingExplicitInputDependencyWithPermissionProblemTest(tools_for_test.TemporaryDirectoryWithChmodTestCase):

    def test_fails_for_inaccessible_inputfile(self):
        os.mkdir('.dlbroot')
        os.mkdir('src')
        os.chmod('src', 0o000)

        regex = (
            r"(?m)\A"
            r"input dependency 'source_file' contains a path of an inaccessible filesystem object: 'src/a\.cpp'\n"
            r"  \| reason: .*\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.run()

        os.chmod('src', 0o600)


class RunWithExplicitInputDependencyThatIsAlsoOutputDependencyTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_input_as_output(self):
        open('a.cpp', 'xb').close()

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = ATool(source_file='a.cpp', object_file='a.cpp')
                t.run()
        msg = "output dependency 'object_file' contains a path that is also an explicit input dependency: 'a.cpp'"
        self.assertEqual(msg, str(cm.exception))


class RunWithExplicitWithDifferentOutputDependenciesForSamePathTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    # noinspection PyAbstractClass
    class BTool(dlb.ex.Tool):
        object_file = dlb.ex.Tool.Output.RegularFile(required=False)
        temp_dir = dlb.ex.Tool.Output.Directory(required=False)
        log_files = dlb.ex.Tool.Output.RegularFile[:](required=False)

    def test_fails_for_two_files(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = RunWithExplicitWithDifferentOutputDependenciesForSamePathTest.BTool(object_file='o', log_files=['o'])
                t.run()
        msg = "output dependencies 'object_file' and 'log_files' both contain the same path: 'o'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_file_and_directory(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = RunWithExplicitWithDifferentOutputDependenciesForSamePathTest.BTool(object_file='o', temp_dir='o/')
                t.run()
        msg = "output dependencies 'temp_dir' and 'object_file' both contain the same path: 'o/'"
        self.assertEqual(msg, str(cm.exception))


class RunFilesystemObjectTypeTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_explicit_input_dependency_of_wrong_type(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open(os.path.join('src', 'b'), 'xb').close()

        t = ATool(source_file='src', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "input dependency 'source_file' contains an invalid path: 'src'\n"
            "  | reason: filesystem object exists, but is not a regular file"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', include_directories=['src/b/'], object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "input dependency 'include_directories' contains an invalid path: 'src/b/'\n"
            "  | reason: filesystem object exists, but is not a directory"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', dummy_file='src/a.cpp', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "input dependency 'dummy_file' contains an invalid path: 'src/a.cpp'\n"  
            "  | reason: filesystem object exists, but is a regular file"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', dummy_file='src', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "input dependency 'dummy_file' contains an invalid path: 'src'\n"
            "  | reason: filesystem object exists, but is a directory"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_conflicting_input_dependency_types(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', include_directories=['src/a.cpp/'], object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "input dependency 'include_directories' contains an invalid path: 'src/a.cpp/'\n"
            "  | reason: filesystem object exists, but is not a directory"
        )
        self.assertEqual(msg, str(cm.exception))


class RunDoesNoRedoIfInputNotModifiedTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_run_causes_redo_only_the_first_time(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open('a.o', 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())

            t = ATool(source_file='src/a.cpp', object_file='a.o')
            self.assertFalse(t.run())

        with dlb.ex.Context():
            t = ATool(source_file='src/a.cpp', object_file='a.o')
            self.assertFalse(t.run())


class RunDoesRedoIfRegularFileInputModifiedTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())

        with open('src/a.cpp', 'wb') as f:
            f.write(b'')  # update mtime (outside root context!)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            self.assertRegex(output.getvalue(), r'\b()mtime has changed\b')
            self.assertFalse(t.run())

        with dlb.ex.Context():
            self.assertFalse(t.run())
            with open('src/a.cpp', 'wb') as f:
                f.write(b'1')  # change size
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            self.assertRegex(output.getvalue(), r'\b()size has changed\b')

        with dlb.ex.Context():
            self.assertFalse(t.run())
            os.chmod(os.path.join('src', 'a.cpp'), 0o000)
            os.chmod(os.path.join('src', 'a.cpp'), 0o600)
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            self.assertRegex(output.getvalue(), r'\b()permissions or owner have changed\b')

        with dlb.ex.Context():
            # replace memo by invalid memo
            rundb = dlb.ex.context._get_rundb()
            rundb.replace_fsobject_inputs(1, {
                dlb.ex.rundb.encode_path(dlb.fs.Path('src/a.cpp')): (True, marshal.dumps(42))
            })

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            self.assertRegex(output.getvalue(), r'\b()state before last successful redo is unknown\b')

        with dlb.ex.Context():
            # replace memo by invalid memo
            rundb = dlb.ex.context._get_rundb()
            rundb.replace_fsobject_inputs(1, {
                dlb.ex.rundb.encode_path(dlb.fs.Path('src/a.cpp')):
                    (True, dlb.ex.rundb.encode_fsobject_memo(dlb.ex.rundb.FilesystemObjectMemo()))
            })

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            self.assertRegex(output.getvalue(), r'\b()filesystem object did not exist\b')


class RunDoesRedoIfNonRegularFileInputModifiedTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        nonregular = os.path.join('src', 'n')

        try:
            os.symlink('a/', nonregular, target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_file='src/n')

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())

        os.remove(nonregular)
        os.symlink('a', nonregular, target_is_directory=False)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            self.assertRegex(output.getvalue(), r'\b()symbolic link target has changed\b')
            self.assertFalse(t.run())

        os.remove(nonregular)
        try:
            os.mkfifo(nonregular)
        except OSError:  # on platform or filesystem that does not support named pipe
            self.assertNotEqual(os.name, 'posix', 'on a typical POSIX system, named pipes should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            self.assertRegex(output.getvalue(), r'\b()type of filesystem object has changed\b')
            self.assertFalse(t.run())


class RunDoesRedoIfInputIsOutputTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open(os.path.join('src', 'b.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        t2 = ATool(source_file='src/b.cpp', object_file='src/a.cpp')

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())

        with dlb.ex.Context():
            self.assertTrue(t2.run())

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            self.assertRegex(output.getvalue(), r'\b()was an output dependency of a redo\b')
            self.assertFalse(t.run())


class RunDoesRedoIfOutputNotAsExpected(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo_if_not_existing(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        with dlb.ex.Context():
            self.assertTrue(t.run())

        os.remove('a.o')
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())

        regex = r"\b()redo necessary because of filesystem object that is an output dependency: 'a\.o'"
        self.assertRegex(output.getvalue(), regex)

    def test_redo_if_not_output_is_directory(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        with dlb.ex.Context():
            self.assertTrue(t.run())

        os.remove('a.o')
        os.mkdir('a.o')
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            regex = (
                r"(?m)\b"
                r"redo necessary because of filesystem object that is an output dependency: 'a\.o' \n"
                r".*  \| reason: filesystem object exists, but is not a regular file\n"
            )
            self.assertRegex(output.getvalue(), regex)


class RunDoesRedoIfExecutionParameterModifiedTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        a_list = ['a', 2]

        class BTool(dlb.ex.Tool):
            XYZ = a_list

            object_file = dlb.ex.Tool.Output.RegularFile()

            async def redo(self, result, context):
                dlb.di.inform("redoing right now")
                open((context.root_path / self.object_file).native, 'wb').close()

        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = BTool(object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())

        a_list.append(None)

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())


class RunDoesRedoIfEnvironmentVariableModifiedTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo_for_explicit(self):
        class BTool(dlb.ex.Tool):
            language = dlb.ex.Tool.Input.EnvVar(name='LANG', restriction=r'.+', example='de_CH')

            async def redo(self, result, context):
                pass

        t = BTool(language='fr_FR')
        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())

        t = BTool(language='fr_FR')
        with dlb.ex.Context():
            self.assertFalse(t.run())

        t = BTool(language='it_IT')
        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())

    def test_redo_for_nonexplicit(self):
        class BTool(dlb.ex.Tool):
            language = dlb.ex.Tool.Input.EnvVar(name='LANG', restriction=r'.+', example='de_CH', explicit=False)

            async def redo(self, result, context):
                pass

        t = BTool()
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', restriction=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = 'fr_FR'
            r = t.run()
            self.assertIsNotNone(r)
            self.assertEqual('fr_FR', r.language.raw)
            self.assertFalse(t.run())

        t = BTool()
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', restriction=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = 'fr_FR'
            self.assertFalse(t.run())

        t = BTool()
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', restriction=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = 'it_IT'
            r = t.run()
            self.assertIsNotNone(r)
            self.assertEqual('it_IT', r.language.raw)
            self.assertFalse(t.run())

    def test_fails_for_nonexplicit_with_invalid_envvar_value(self):
        class BTool(dlb.ex.Tool):
            language = dlb.ex.Tool.Input.EnvVar(name='LANG', restriction=r'[a-z]+_[A-Z]+',
                                                example='de_CH', explicit=False)

            async def redo(self, result, context):
                pass

        t = BTool()
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', restriction=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = '_'
            with self.assertRaises(dlb.ex.RedoError) as cm:
                t.run()
            msg = (
                "input dependency 'language' cannot use environment variable 'LANG'\n"
                "  | reason: value is invalid with respect to restriction: '_'"
            )
            self.assertEqual(msg, str(cm.exception))

    def test_redo_for_explicit_and_nonexplicit(self):
        class BTool(dlb.ex.Tool):
            language = dlb.ex.Tool.Input.EnvVar(name='LANG', restriction=r'.+', example='de_CH', explicit=False)
            language2 = dlb.ex.Tool.Input.EnvVar(name='LANG', restriction=r'.+', example='de_CH')

            async def redo(self, result, context):
                pass

        t = BTool(language2='it_IT')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', restriction=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = 'fr_FR'
            r = t.run()
            self.assertIsNotNone(r)
            self.assertEqual('it_IT', r.language.raw)
            self.assertEqual('it_IT', r.language2.raw)
            self.assertFalse(t.run())

        t = BTool(language2='it_IT')
        with dlb.ex.Context():
            self.assertFalse(t.run())

        t = BTool(language2='fr_FR')
        with dlb.ex.Context():
            r = t.run()
            self.assertIsNotNone(r)
            self.assertEqual('fr_FR', r.language.raw)
            self.assertEqual('fr_FR', r.language2.raw)
            self.assertFalse(t.run())


class RunDoesRedoIfAccordingToLastRedoReturnValueTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo_always(self):
        class BTool(dlb.ex.Tool):
            async def redo(self, result, context):
                return True

        t = BTool()
        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertTrue(t.run())
            self.assertTrue(t.run())

    def test_redo_cannot_forbid_next_redo(self):
        a_list = ['a', 2]

        class BTool(dlb.ex.Tool):
            XYZ = a_list

            async def redo(self, result, context):
                return False  # like None

        t = BTool()
        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())

        a_list.append(None)

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertFalse(t.run())


class RunRemovesObstructingExplicitOutputBeforeRedoTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo_ignores_nonexistent_output_file(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertTrue(t.run())
        self.assertFalse(os.path.exists('d'))

    def test_redo_does_not_remove_nonobstructing_outputs(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open('a.o', 'xb').close()
        os.mkdir('d/')

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertTrue(t.run())
        self.assertTrue(os.path.exists('a.o'))
        self.assertTrue(os.path.exists('d'))

    def test_redo_removes_obstructing_outputs(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open('d', 'xb').close()
        os.mkdir('a.o')

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertTrue(t.run())
        self.assertTrue(os.path.isfile('a.o'))
        self.assertFalse(os.path.exists('d'))

    def test_run_without_redo_does_not_remove_output_files(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertTrue(t.run())

        os.mkdir('d')

        with dlb.ex.Context():
            self.assertFalse(t.run())

        self.assertTrue(os.path.isfile('a.o'))
        self.assertTrue(os.path.isdir('d'))


class ExecutionParameterTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_if_execution_parameter_not_fundamental(self):
        # noinspection PyAbstractClass
        class BTool(dlb.ex.Tool):
            XY = dlb.fs.Path('.')

        with dlb.ex.Context():
            t = BTool()
            with self.assertRaises(dlb.ex.ExecutionParameterError) as cm:
                t.run()
            msg = (
                "value of execution parameter 'XY' is not fundamental: Path('./')\n"
                "  | an object is fundamental if it is None, or of type 'bool', 'int', 'float', 'complex', 'str', "
                "'bytes', or a mapping or iterable of only such objects"
            )
            self.assertEqual(msg, str(cm.exception))
