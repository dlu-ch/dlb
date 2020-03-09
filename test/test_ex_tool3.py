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
import dlb.fs.manip
import dlb.ex.rundb
import marshal
import io
import pathlib
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
        with open((context.root_path / self.object_file).native, 'wb'):
            pass


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

        with pathlib.Path('a.cpp').open('xb'):
            pass

        with dlb.ex.Context() as c:
            t = ATool(source_file=c.root_path / 'a.cpp', object_file='a.o')
            r = t.run()
            self.assertEqual(c.root_path / 'a.cpp', r.source_file)

    def test_absolute_can_be_outside_managed_tree(self):
        with pathlib.Path('x.cpp').open('xb'):
            pass

        os.mkdir('t')
        with tools_for_test.DirectoryChanger('t'):
            os.mkdir('.dlbroot')

            with pathlib.Path('a.cpp').open('xb'):
                pass

            with dlb.ex.Context() as c:
                t = ATool(source_file=c.root_path / '../x.cpp', object_file='a.o')
                t.run()


class RunWithExplicitOutputDependencyTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_nonnormalized_outputfile_path(self):
        with pathlib.Path('a.cpp').open('xb'):
            pass

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
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()
        src.chmod(0o000)

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
        with pathlib.Path('a.cpp').open('xb'):
            pass

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
        log_files = dlb.ex.Tool.Output.RegularFile[:](required=False, unique=False)

    def test_fails_for_two_files(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = RunWithExplicitWithDifferentOutputDependenciesForSamePathTest.BTool(object_file='o', log_files=['o'])
                t.run()
        msg = "output dependencies 'object_file' and 'log_files' both contain the same path: 'o'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_two_files_in_same_dependency(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = RunWithExplicitWithDifferentOutputDependenciesForSamePathTest.BTool(log_files=['o', 'o'])
                t.run()
        msg = "output dependency 'log_files' contains the same path more than once: 'o'"
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
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass
        with (src / 'b').open('xb'):
            pass

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
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

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
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass
        with pathlib.Path('a.o').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
            self.assertIsNone(t.run())

            t = ATool(source_file='src/a.cpp', object_file='a.o')
            self.assertIsNone(t.run())

        with dlb.ex.Context():
            t = ATool(source_file='src/a.cpp', object_file='a.o')
            self.assertIsNone(t.run())


class RunDoesRedoIfRegularFileInputModifiedTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
            self.assertIsNone(t.run())

        with open('src/a.cpp', 'wb') as f:
            f.write(b'')  # update mtime (outside root context!)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()mtime has changed\b')
            self.assertIsNone(t.run())

        with dlb.ex.Context():
            self.assertIsNone(t.run())
            with open('src/a.cpp', 'wb') as f:
                f.write(b'1')  # change size
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()size has changed\b')

        with dlb.ex.Context():
            self.assertIsNone(t.run())
            (src / 'a.cpp').chmod(0o000)
            (src / 'a.cpp').chmod(0o600)
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()permissions or owner have changed\b')

        with dlb.ex.Context():
            # replace memo by invalid memo
            rundb = dlb.ex.context._get_rundb()
            rundb.replace_fsobject_inputs(1, {
                dlb.ex.rundb.encode_path(dlb.fs.Path('src/a.cpp')): (True, marshal.dumps(42))
            })

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()state before last successful redo is unknown\b')

        with dlb.ex.Context():
            # replace memo by invalid memo
            rundb = dlb.ex.context._get_rundb()
            rundb.replace_fsobject_inputs(1, {
                dlb.ex.rundb.encode_path(dlb.fs.Path('src/a.cpp')):
                    (True, dlb.ex.rundb.encode_fsobject_memo(dlb.fs.manip.FilesystemObjectMemo()))
            })

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()filesystem object did not exist\b')


class RunDoesRedoIfNonRegularFileInputModifiedTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        src = pathlib.Path('src')
        src.mkdir()
        with (src / 'a.cpp').open('xb'):
            pass

        nonregular = src / 'n'

        try:
            nonregular.symlink_to('a/', target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_file='src/n')

        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
            self.assertIsNone(t.run())

        nonregular.unlink()
        nonregular.symlink_to('a', target_is_directory=False)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()symbolic link target has changed\b')
            self.assertIsNone(t.run())

        nonregular.unlink()
        try:
            os.mkfifo(nonregular)
        except OSError:  # on platform or filesystem that does not support named pipe
            self.assertNotEqual(os.name, 'posix', 'on a typical POSIX system, named pipes should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()type of filesystem object has changed\b')
            self.assertIsNone(t.run())


class RunDoesRedoIfInputIsOutputTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass
        with (src / 'b.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        t2 = ATool(source_file='src/b.cpp', object_file='src/a.cpp')

        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
            self.assertIsNone(t.run())

        with dlb.ex.Context():
            self.assertIsNotNone(t2.run())

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()was an output dependency of a redo\b')
            self.assertIsNone(t.run())


class RunDoesRedoIfOutputNotAsExpected(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo_if_not_existing(self):
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())

        pathlib.Path('a.o').unlink()
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())

        regex = r"\b()redo necessary because of filesystem object that is an output dependency: 'a\.o'"
        self.assertRegex(output.getvalue(), regex)

    def test_redo_if_not_output_is_directory(self):
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())

        pathlib.Path('a.o').unlink()
        pathlib.Path('a.o').mkdir()
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
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
                with open((context.root_path / self.object_file).native, 'wb'):
                    pass

        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

        t = BTool(object_file='a.o')

        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
            self.assertIsNone(t.run())

        a_list.append(None)

        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
            self.assertIsNone(t.run())


class RunRedoRemovesObstructionExplicitOutputTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo_ignores_nonexistent_output_file(self):
        os.mkdir('src')
        with open(os.path.join('src', 'a.cpp'), 'xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
        self.assertFalse(os.path.exists('d'))

    def test_redo_does_not_remove_nonobstructing_outputs(self):
        os.mkdir('src')
        with open(os.path.join('src', 'a.cpp'), 'xb'):
            pass
        with open('a.o', 'xb'):
            pass
        os.mkdir('d/')

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
        self.assertTrue(os.path.exists('a.o'))
        self.assertTrue(os.path.exists('d'))

    def test_redo_removes_obstructing_outputs(self):
        os.mkdir('src')
        with open(os.path.join('src', 'a.cpp'), 'xb'):
            pass
        with open('d', 'xb'):
            pass
        os.mkdir('a.o')

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
        self.assertTrue(os.path.isfile('a.o'))
        self.assertFalse(os.path.exists('d'))

    def test_run_without_redo_does_not_remove_output_files(self):
        os.mkdir('src')
        with open(os.path.join('src', 'a.cpp'), 'xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())

        os.mkdir('d')

        with dlb.ex.Context():
            self.assertIsNone(t.run())

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
