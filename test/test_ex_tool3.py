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

    def redo(self, result, context):
        dlb.di.inform("redoing right now")

        with (context.root_path / self.object_file).native.raw.open('xb'):
            pass


class RunWithoutRedoTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_without_redo(self):

        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()

        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context():
            t = BTool(object_file='a.o')
            with self.assertRaises(NotImplementedError):
                t.run()


class RunWithMissingExplicitInputDependencyTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_nonexistent_inputfile(self):
        pathlib.Path('.dlbroot').mkdir()

        regex = (
            r"\A()input dependency 'source_file' contains a path of an non-existing "
            r"filesystem object: 'src/a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyCheckError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.run()

        regex = (
            r"\A()input dependency 'source_file' contains a path of an non-existing "
            r"filesystem object: 'src/b/\.\./a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyCheckError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/b/../a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.run()

    def test_fails_for_nonnormalized_inputfile_path(self):
        pathlib.Path('.dlbroot').mkdir()

        regex = (
            r"(?m)\A"
            r"input dependency 'source_file' contains a path that is not a managed tree path: '\.\./a\.cpp'\n"
            r"  | reason: is an upwards path: '\.\.[\\/]+a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyCheckError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='../a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.run()


class RunWithExplicitOutputDependencyTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_nonnormalized_outputfile_path(self):
        pathlib.Path('.dlbroot').mkdir()

        with pathlib.Path('a.cpp').open('xb'):
            pass

        regex = (
            r"(?m)\A"
            r"output dependency 'object_file' contains a path that is not a managed tree path: '\.\./a\.o'\n"
            r"  | reason: is an upwards path: '\.\.[\\/]+a\.o'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyCheckError, regex):
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
        with self.assertRaisesRegex(dlb.ex.DependencyCheckError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.run()

        os.chmod('src', 0o600)


class RunWithExplicitInputDependencyThatIsAlsoOutputDependencyTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_input_as_output(self):
        pathlib.Path('.dlbroot').mkdir()

        with pathlib.Path('a.cpp').open('xb'):
            pass

        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t = ATool(source_file='a.cpp', object_file='a.cpp')
                t.run()
        msg = "output dependency 'object_file' contains a path that is also an explicit input dependency: 'a.cpp'"
        self.assertEqual(msg, str(cm.exception))


class RunFilesystemObjectTypeTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_explicit_input_dependency_of_wrong_type(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass
        with (src / 'b').open('xb'):
            pass

        t = ATool(source_file='src', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "invalid value of dependency 'source_file': 'src'\n"
            "  | reason: filesystem object exists, but is not a regular file"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', include_directories=['src/b/'], object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "invalid value of dependency 'include_directories': 'src/b/'\n"
            "  | reason: filesystem object exists, but is not a directory"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', dummy_file='src/a.cpp', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "invalid value of dependency 'dummy_file': 'src/a.cpp'\n"  
            "  | reason: filesystem object exists, but is a regular file"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', dummy_file='src', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "invalid value of dependency 'dummy_file': 'src'\n"
            "  | reason: filesystem object exists, but is a directory"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_conflicting_input_dependency_types(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', include_directories=['src/a.cpp/'], object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "invalid value of dependency 'include_directories': 'src/a.cpp/'\n"
            "  | reason: filesystem object exists, but is not a directory"
        )
        self.assertEqual(msg, str(cm.exception))


class RunDoesNoRedoForIfInputNotModifiedTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_run_causes_redo_only_the_first_time(self):
        pathlib.Path('.dlbroot').mkdir()
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


class RunDoesRedoIfRegularFileInputModifiedTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_redo(self):
        pathlib.Path('.dlbroot').mkdir()
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


class RunDoesRedoIfNonRegularFileInputModifiedTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_redo(self):
        pathlib.Path('.dlbroot').mkdir()
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


class RunDoesRedoIfInputIsOutputTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_redo(self):
        pathlib.Path('.dlbroot').mkdir()
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
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertIsNotNone(t.run())
            self.assertRegex(output.getvalue(), r'\b()was an output dependency of a redo\b')
            self.assertIsNone(t.run())


class RunDoesRedoIfOutputNotAsExpected(tools_for_test.TemporaryDirectoryTestCase):

    def test_redo_if_not_existing(self):
        pathlib.Path('.dlbroot').mkdir()
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
        pathlib.Path('.dlbroot').mkdir()
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


class RunRedoRemovesExplicitOutputTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_redo_ignores_unexisting_output_file(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
        self.assertFalse(pathlib.Path('d').exists())

    def test_redo_removes_existing_output_dir(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass
        pathlib.Path('d').mkdir()

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
        self.assertFalse(pathlib.Path('d').exists())

    def test_redo_removes_existing_output_file(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass
        with pathlib.Path('d').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
        self.assertFalse(pathlib.Path('d').exists())

    def test_run_without_redo_does_not_remove_output_file(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertIsNotNone(t.run())

        pathlib.Path('d').mkdir()
        with dlb.ex.Context():
            self.assertIsNone(t.run())
        self.assertTrue(pathlib.Path('d').exists())  # still exists
