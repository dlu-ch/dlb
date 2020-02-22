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

    def redo(self):
        dlb.di.inform("redoing right now")
        return 1


class RunWithMissingExplicitInputDependencyTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_inexisting_inputfile(self):
        pathlib.Path('.dlbroot').mkdir()

        regex = (
            r"\Ainput dependency 'source_file' contains a path of an non-existing "
            r"filesystem object: 'src[\\/]+a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyCheckError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.out', include_directories=['src/serdes/'])
                t.run()

    def test_fails_for_nonnormalized_inputfile_path(self):
        pathlib.Path('.dlbroot').mkdir()

        regex = (
            r"(?m)\A"
            r"input dependency 'source_file' contains a path that is not a managed tree path: '\.\.[\\/]+a\.cpp'\n"
            r"  | reason: is an upwards path: '\.\.[\\/]+a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyCheckError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='../a.cpp', object_file='out/a.out', include_directories=['src/serdes/'])
                t.run()


class RunWithMissingExplicitInputDependencyWithPermissionProblemTest(tools_for_test.TemporaryDirectoryWithChmodTestCase):

    def test_fails_for_inaccessible_inputfile(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()
        src.chmod(0o000)

        regex = (
            r"(?m)\A"
            r"input dependency 'source_file' contains a path of an inaccessible filesystem object: 'src[\\/]+a\.cpp'\n"
            r"  \| reason: .*\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyCheckError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.out', include_directories=['src/serdes/'])
                t.run()

        os.chmod('src', 0o600)


class RunFilesystemObjectTypeTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_explicit_input_dependency_of_wrong_type(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass
        with (src / 'b').open('xb'):
            pass

        t = ATool(source_file='src', object_file='a.out')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "invalid value of dependency 'source_file': 'src'\n"
            "  | reason: filesystem object exists, but is not a regular file"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', include_directories=['src/b/'], object_file='a.out')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "invalid value of dependency 'include_directories': 'src/b/'\n"
            "  | reason: filesystem object exists, but is not a directory"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', dummy_file='src/a.cpp', object_file='a.out')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "invalid value of dependency 'dummy_file': 'src/a.cpp'\n"  
            "  | reason: filesystem object exists, but is a regular file"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', dummy_file='src', object_file='a.out')
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

        t = ATool(source_file='src/a.cpp', include_directories=['src/a.cpp/'], object_file='a.out')
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

        t = ATool(source_file='src/a.cpp', object_file='a.out')

        with dlb.ex.Context():
            self.assertIsNotNone(t.run())
            self.assertIsNone(t.run())

            t = ATool(source_file='src/a.cpp', object_file='a.out')
            self.assertIsNone(t.run())

        with dlb.ex.Context():
            t = ATool(source_file='src/a.cpp', object_file='a.out')
            self.assertIsNone(t.run())


class RunDoesRedoIfRegularFileInputModifiedTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_redo(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.out')

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

        t = ATool(source_file='src/a.cpp', object_file='a.out', dummy_file='src/n')

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


class RunDoesRedoIfInputIsOutput(tools_for_test.TemporaryDirectoryTestCase):

    def test_redo(self):
        pathlib.Path('.dlbroot').mkdir()
        src = pathlib.Path('src')
        src.mkdir()

        with (src / 'a.cpp').open('xb'):
            pass
        with (src / 'b.cpp').open('xb'):
            pass

        t = ATool(source_file='src/a.cpp', object_file='a.out')
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
