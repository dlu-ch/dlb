# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import dlb.ex
import sys
import os.path
import marshal
import tempfile
import zipfile
import io
import unittest


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.input.RegularFile()
    object_file = dlb.ex.output.RegularFile()
    log_file = dlb.ex.output.RegularFile(required=False, explicit=False)
    include_directories = dlb.ex.input.Directory[:](required=False)
    dummy_file = dlb.ex.input.NonRegularFile(required=False)
    dummy_dir = dlb.ex.output.Directory(required=False)

    async def redo(self, result, context):
        dlb.di.inform("redoing right now")
        open((context.root_path / self.object_file).native, 'wb').close()


class FTool(dlb.ex.Tool):
    source_file = dlb.ex.input.RegularFile()
    object_file = dlb.ex.output.RegularFile()
    included_files = dlb.ex.input.RegularFile[:](explicit=False)

    async def redo(self, result, context):
        dlb.di.inform("redoing right now")

        with (context.root_path / self.object_file).native.raw.open('wb'):
            pass

        result.included_files = [dlb.fs.Path('a.h'), dlb.fs.Path('b.h')]


class ThisIsAUnitTest(unittest.TestCase):
    pass


class FailsWithoutRedoTest(testenv.TemporaryWorkingDirectoryTestCase):

    # noinspection PyAbstractClass
    def test_fails_without_redo(self):

        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.output.RegularFile()

        with self.assertRaises(NotImplementedError):
            with dlb.ex.Context():
                t = BTool(object_file='a.o')
                t.start()


class FailsWithMissingExplicitInputDependencyTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_nonexistent_inputfile(self):
        regex = (
            r"\A()input dependency 'source_file' contains a path of a non-existent "
            r"filesystem object: 'src/a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.start()

        regex = (
            r"\A()input dependency 'source_file' contains a path of a non-existent "
            r"filesystem object: 'src/b/\.\./a\.cpp'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='src/b/../a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.start()

    def test_fails_for_nonnormalized_inputfile_path(self):
        regex = (
            r"(?m)\A"
            r"input dependency 'source_file' contains an invalid path: '\.\./a\.cpp'\n"
            r"  | reason: not in managed tree\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            with dlb.ex.Context():
                t = ATool(source_file='../a.cpp', object_file='out/a.o', include_directories=['src/serdes/'])
                t.start()


class FailsWithMissingExplicitInputDependencyWithPermissionProblemTest(
        testenv.TemporaryDirectoryWithChmodTestCase,
        testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_inaccessible_inputfile(self):
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
                t.start()

        os.chmod('src', 0o600)


class FailsWithExplicitInputDependencyThatIsAlsoOutputDependencyTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_input_as_output(self):
        open('a.cpp', 'xb').close()

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = ATool(source_file='a.cpp', object_file='a.cpp')
                t.start()
        msg = "output dependency 'object_file' contains a path that is also an explicit input dependency: 'a.cpp'"
        self.assertEqual(msg, str(cm.exception))


class FailsWithExplicitOutputDependencyOutsideTest(testenv.TemporaryWorkingDirectoryTestCase):

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
                t.start()


class FailsWithExplicitWithDifferentOutputDependenciesForSamePathTest(testenv.TemporaryWorkingDirectoryTestCase):

    # noinspection PyAbstractClass
    class BTool(dlb.ex.Tool):
        object_file = dlb.ex.output.RegularFile(required=False)
        temp_dir = dlb.ex.output.Directory(required=False)
        log_files = dlb.ex.output.RegularFile[:](required=False)

    def test_fails_for_two_files(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = FailsWithExplicitWithDifferentOutputDependenciesForSamePathTest.BTool(
                        object_file='o', log_files=['o'])
                t.start()
        msg = "output dependencies 'object_file' and 'log_files' both contain the same path: 'o'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_file_and_directory(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = FailsWithExplicitWithDifferentOutputDependenciesForSamePathTest.BTool(
                        object_file='o', temp_dir='o/')
                t.start()
        msg = "output dependencies 'temp_dir' and 'object_file' both contain the same path: 'o/'"
        self.assertEqual(msg, str(cm.exception))


class FailsWithDifferentInputDependenciesForSameEnvVarTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails(self):
        # noinspection PyAbstractClass
        class BTool(dlb.ex.Tool):
            a_var = dlb.ex.input.EnvVar(name='XY', pattern='.*', example='')
            b_var = dlb.ex.input.EnvVar(name='XY', pattern='.*', example='', explicit=False)

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t = BTool(a_var='a')
                t.start()
        msg = "input dependencies 'b_var' and 'a_var' both define the same environment variable: 'XY'"
        self.assertEqual(msg, str(cm.exception))


class FailWithInputDependenciesOfWrongType(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_explicit_input_dependency_of_wrong_type(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open(os.path.join('src', 'b'), 'xb').close()

        t = ATool(source_file='src', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.start()
        msg = (
            "input dependency 'source_file' contains an invalid path: 'src'\n"
            "  | reason: filesystem object exists but is not a regular file"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', include_directories=['src/b/'], object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.start()
        msg = (
            "input dependency 'include_directories' contains an invalid path: 'src/b/'\n"
            "  | reason: filesystem object exists but is not a directory"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', dummy_file='src/a.cpp', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.start()
        msg = (
            "input dependency 'dummy_file' contains an invalid path: 'src/a.cpp'\n"  
            "  | reason: filesystem object exists but is a regular file"
        )
        self.assertEqual(msg, str(cm.exception))

        t = ATool(source_file='src/a.cpp', dummy_file='src', object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.start()
        msg = (
            "input dependency 'dummy_file' contains an invalid path: 'src'\n"
            "  | reason: filesystem object exists but is a directory"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_conflicting_input_dependency_types(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', include_directories=['src/a.cpp/'], object_file='a.o')
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            with dlb.ex.Context():
                t.start()
        msg = (
            "input dependency 'include_directories' contains an invalid path: 'src/a.cpp/'\n"
            "  | reason: filesystem object exists but is not a directory"
        )
        self.assertEqual(msg, str(cm.exception))


class FailsWithInvalidExecutionParameterTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_if_execution_parameter_not_fundamental(self):
        # noinspection PyAbstractClass
        class BTool(dlb.ex.Tool):
            XY = dlb.fs.Path('.')

        with dlb.ex.Context():
            t = BTool()
            with self.assertRaises(dlb.ex.ExecutionParameterError) as cm:
                t.start()
            msg = (
                "value of execution parameter 'XY' is not fundamental: Path('./')\n"
                "  | an object is fundamental if it is None, or of type 'bool', 'int', 'float', 'complex', 'str', "
                "'bytes', or a mapping or iterable of only such objects"
            )
            self.assertEqual(msg, str(cm.exception))

    def test_fails_if_execution_parameter_from_constructor_not_fundamental(self):
        # noinspection PyAbstractClass
        class BTool(dlb.ex.Tool):
            XY = [1, '?']

        with dlb.ex.Context():
            with self.assertRaises(TypeError) as cm:
                BTool(XY=dlb.fs.Path('.'))
            msg = "attribute 'XY' of base class may only be overridden with a value which is a <class 'list'>"
            self.assertEqual(msg, str(cm.exception))


class NoRedoIfInputNotModifiedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_run_causes_redo_only_the_first_time(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open('a.o', 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

            t = ATool(source_file='src/a.cpp', object_file='a.o')
            self.assertFalse(t.start())

        with dlb.ex.Context():
            t = ATool(source_file='src/a.cpp', object_file='a.o')
            self.assertFalse(t.start())


class RedoIfNoKnownRedoBefore(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        class BTool(dlb.ex.Tool):
            async def redo(self, result, context):
                pass

        t = BTool()
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r'\b()I redo necessary because not run before\n')
            self.assertFalse(t.start())


class RedoIfRegularFileInputModifiedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        with open('src/a.cpp', 'wb') as f:
            f.write(b'')  # update mtime (outside root context!)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r'\b()mtime has changed\b')
            self.assertFalse(t.start())

        with dlb.ex.Context():
            self.assertFalse(t.start())
            with open('src/a.cpp', 'wb') as f:
                f.write(b'1')  # change size
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r'\b()size has changed\b')

        with dlb.ex.Context():
            self.assertFalse(t.start())
            # replace memo by invalid memo
            rundb = dlb.ex._context._get_rundb()
            rundb.update_dependencies_and_state(1, info_by_encoded_path={
                dlb.ex._rundb.encode_path(dlb.fs.Path('src/a.cpp')): (True, marshal.dumps(42))
            })

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r'\b()state before last successful redo is unknown\b')

        with dlb.ex.Context():
            # replace memo by invalid memo
            rundb = dlb.ex._context._get_rundb()
            rundb.update_dependencies_and_state(1, info_by_encoded_path={
                dlb.ex._rundb.encode_path(dlb.fs.Path('src/a.cpp')):
                    (True, dlb.ex._rundb.encode_fsobject_memo(dlb.ex._rundb.FilesystemObjectMemo()))
            })

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r'\b()filesystem object did not exist\b')


class RedoIfRegularFileInputChmodModifiedTest(testenv.TemporaryDirectoryWithChmodTestCase,
                                              testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        with dlb.ex.Context():
            os.chmod(os.path.join('src', 'a.cpp'), 0o000)
            os.chmod(os.path.join('src', 'a.cpp'), 0o600)
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r'\b()permissions or owner have changed\b')


class RedoIfNonRegularFileInputModifiedTest(testenv.TemporaryWorkingDirectoryTestCase):

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
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        os.remove(nonregular)
        os.symlink('a', nonregular, target_is_directory=False)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r'\b()symbolic link target has changed\b')
            self.assertFalse(t.start())

        os.remove(nonregular)
        try:
            os.mkfifo(nonregular)
        except OSError:  # on platform or filesystem that does not support named pipe
            self.assertNotEqual(os.name, 'posix', 'on a typical POSIX system, named pipes should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r'\b()type of filesystem object has changed\b')
            self.assertFalse(t.start())


class RedoIfInputIsOutputTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open(os.path.join('src', 'b.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        t2 = ATool(source_file='src/b.cpp', object_file='src/a.cpp')

        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        with dlb.ex.Context():
            self.assertTrue(t2.start())

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(),
                             r'\b()output dependency of a tool instance potentially changed by a redo\b')
            self.assertFalse(t.start())


class RedoIfOutputNotAsExpected(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo_if_not_existing(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        with dlb.ex.Context():
            self.assertTrue(t.start())

        os.remove('a.o')
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())

        regex = (
            r"(?m)\n"
            r"( *)D explicit output dependencies\.\.\. \[[+.0-9]+s\]\n" 
            r"\1  I redo necessary because of filesystem object: 'a\.o' \n"
        )
        self.assertRegex(output.getvalue(), regex)

    def test_redo_if_not_output_is_directory(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o')
        with dlb.ex.Context():
            self.assertTrue(t.start())

        os.remove('a.o')
        os.mkdir('a.o')
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            regex = (
                r"(?m)\n"
                r"( *)D explicit output dependencies\.\.\. \[[+.0-9]+s\]\n"
                r"\1  I redo necessary because of filesystem object: 'a\.o' \n"
                r"\1    \| reason: filesystem object exists but is not a regular file\n"
            )
            self.assertRegex(output.getvalue(), regex)


class RedoIfInputSwitchesTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        class BTool(dlb.ex.Tool):
            input_a = dlb.ex.output.RegularFile()
            input_b = dlb.ex.output.RegularFile()
            object_file = dlb.ex.output.RegularFile()

            async def redo(self, result, context):
                dlb.di.inform("redoing right now")
                open((context.root_path / self.object_file).native, 'wb').close()

        open('a.c', 'xb').close()
        open('b.c', 'xb').close()

        t = BTool(input_a='a.c', input_b='b.c', object_file='a.o')
        fingerprint = t.fingerprint
        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        t = BTool(input_b='a.c', input_a='b.c', object_file='a.o')
        self.assertNotEqual(fingerprint, t.fingerprint)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r"\b()I redo necessary because not run before\n")
            self.assertFalse(t.start())


class RedoIfInputIsRemovedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        class BTool(dlb.ex.Tool):
            input_files = dlb.ex.output.RegularFile[:]()
            object_file = dlb.ex.output.RegularFile()

            async def redo(self, result, context):
                dlb.di.inform("redoing right now")
                open((context.root_path / self.object_file).native, 'wb').close()

        open('a.c', 'xb').close()
        open('b.c', 'xb').close()

        t = BTool(input_files=['a.c', 'b.c'], object_file='a.o')
        fingerprint = t.fingerprint
        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        t = BTool(input_files=['a.c'], object_file='a.o')
        self.assertNotEqual(fingerprint, t.fingerprint)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r"\b()I redo necessary because not run before\n")
            self.assertFalse(t.start())


class RedoIfInputOrderIsChangedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo(self):
        class BTool(dlb.ex.Tool):
            input_files = dlb.ex.output.RegularFile[:]()
            object_file = dlb.ex.output.RegularFile()

            async def redo(self, result, context):
                dlb.di.inform("redoing right now")
                open((context.root_path / self.object_file).native, 'wb').close()

        open('a.c', 'xb').close()
        open('b.c', 'xb').close()

        t = BTool(input_files=['a.c', 'b.c'], object_file='a.o')
        fingerprint = t.fingerprint
        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        t = BTool(input_files=['b.c', 'a.c'], object_file='a.o')
        self.assertNotEqual(fingerprint, t.fingerprint)
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r"\b()I redo necessary because not run before\n")
            self.assertFalse(t.start())


class RedoIfExecutionParameterModifiedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo_if_change_on_instance_without_change_of_class(self):
        a_list = ['a', 2] * 10

        class BTool(dlb.ex.Tool):
            XYZ = a_list

            async def redo(self, result, context):
                pass

        t = BTool()

        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        # noinspection PyTypeChecker
        a_list.append(None)

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())  # note: different tool instance
            self.assertRegex(output.getvalue(), r"\b()I redo necessary because not run before\n")

            self.assertFalse(t.start())

    def test_redo_if_change_by_argument(self):

        class BTool(dlb.ex.Tool):
            XYZ = []

            async def redo(self, result, context):
                pass

        t = BTool()
        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        t = BTool(XYZ=[])
        with dlb.ex.Context():
            self.assertFalse(t.start())

        t = BTool(XYZ=[1])
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())  # note: different tool instance
            self.assertRegex(output.getvalue(), r"\b()I redo necessary because not run before\n")

            self.assertFalse(t.start())


class RedoIfEnvironmentVariableModifiedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo_for_explicit(self):
        class BTool(dlb.ex.Tool):
            language_code = dlb.ex.input.EnvVar(name='LANG', pattern=r'.+', example='de_CH')

            async def redo(self, result, context):
                pass

        t = BTool(language_code='fr_FR')
        with dlb.ex.Context():
            self.assertTrue(t.start())

        t = BTool(language_code='it_IT')
        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())  # note: different tool instance
            self.assertRegex(output.getvalue(), r"\b()I redo necessary because not run before\n")

            self.assertFalse(t.start())

    def test_redo_for_nonexplicit(self):
        class BTool(dlb.ex.Tool):
            language_code = dlb.ex.input.EnvVar(name='LANG', pattern=r'.+', example='de_CH', explicit=False)

            async def redo(self, result, context):
                pass

        t = BTool()
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', pattern=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = 'fr_FR'
            r = t.start()
            self.assertIsNotNone(r)
            self.assertEqual('fr_FR', r.language_code.raw)
            self.assertFalse(t.start())

        t = BTool()
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', pattern=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = 'fr_FR'
            self.assertFalse(t.start())

        t = BTool()  # note: same tool instance
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', pattern=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = 'it_IT'

            output = io.StringIO()
            dlb.di.set_output_file(output)
            r = t.start()
            self.assertRegex(output.getvalue(), r"\b()I redo necessary because of changed environment variable\n")

            self.assertIsNotNone(r)
            self.assertEqual('it_IT', r.language_code.raw)
            self.assertFalse(t.start())

    def test_fails_for_nonexplicit_with_invalid_envvar_value(self):
        class BTool(dlb.ex.Tool):
            language_code = dlb.ex.input.EnvVar(name='LANG', pattern=r'[a-z]+_[A-Z]+', example='de_CH', explicit=False)

            async def redo(self, result, context):
                pass

        t = BTool()
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', pattern=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = '_'
            with self.assertRaises(dlb.ex.RedoError) as cm:
                t.start()
            msg = (
                "input dependency 'language_code' cannot use environment variable 'LANG'\n"
                "  | reason: value '_' is not matched by validation pattern '[a-z]+_[A-Z]+'"
            )
            self.assertEqual(msg, str(cm.exception))


class RedoIfAccordingToLastRedoReturnValueTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo_always(self):
        class BTool(dlb.ex.Tool):
            async def redo(self, result, context):
                return True

        t = BTool()
        with dlb.ex.Context():
            self.assertTrue(t.start())  # because not run yet
            self.assertTrue(t.start())

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            self.assertRegex(output.getvalue(), r"\b()I redo requested by last successful redo\n")

    def test_redo_cannot_forbid_next_redo(self):
        a_list = ['a', 2]

        class BTool(dlb.ex.Tool):
            XYZ = a_list

            async def redo(self, result, context):
                return False  # like None

        t = BTool()
        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())

        a_list.append(None)

        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertFalse(t.start())


class RedoIfForced(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo_when_forced(self):
        class BTool(dlb.ex.Tool):
            async def redo(self, result, context):
                pass

        t = BTool()
        with dlb.ex.Context():
            self.assertTrue(t.start())  # because not run yet
            self.assertFalse(t.start())
            self.assertTrue(t.start(force_redo=True))

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start(force_redo=True))
            self.assertRegex(output.getvalue(), r"\b()I redo requested by start\(\)\n")


class RedoIfExplicitInputDependencyChangedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_new_or_missing_dependency_causes_redo(self):
        open('a.cpp', 'xb').close()

        t = FTool(source_file='a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.start())

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())  # because new dependency
            regex = (
                r"(?m)\b"
                r"redo necessary because of filesystem object: 'a\.h' \n"
                r" *  \| reason: was a new dependency or was potentially changed by a redo\n"
            )
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.start())

        open('a.h', 'xb').close()

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())  # because new dependency
            regex = (
                r"(?m)\b"
                r"redo necessary because of filesystem object: 'a\.h' \n"
                r" *  \| reason: existence has changed\n"
            )
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.start())

        os.remove('a.h')

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())  # because of new dependency
            regex = (
                r"(?m)\b"
                r"redo necessary because of non-existent filesystem object: 'a.h'\n"
            )
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.start())

    def test_invalid_dependency_causes_redo(self):
        open('a.cpp', 'xb').close()
        open('a.h', 'xb').close()

        t = FTool(source_file='a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertTrue(t.start())  # because of new dependency
            self.assertFalse(t.start())

        with dlb.ex.Context():
            # replace memo by invalid memo
            rundb = dlb.ex._context._get_rundb()
            info_by_encoded_path = rundb.get_fsobject_inputs(1)
            info_by_encoded_path[dlb.ex._rundb.encode_path(dlb.fs.Path('a.h'))] = (False, marshal.dumps(42))
            rundb.update_dependencies_and_state(1, info_by_encoded_path=info_by_encoded_path)

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())  # because new dependency
            regex = (
                r"(?m)\b"
                r"redo necessary because of filesystem object: 'a.h' \n"
                r" *  \| reason: state before last successful redo is unknown\n"
            )
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.start())

        with dlb.ex.Context():
            # add dependency with invalid encoded path
            rundb = dlb.ex._context._get_rundb()
            info_by_encoded_path = rundb.get_fsobject_inputs(1)
            info_by_encoded_path['a/../'] = (False, None)
            rundb.update_dependencies_and_state(1, info_by_encoded_path=info_by_encoded_path)

            output = io.StringIO()
            dlb.di.set_output_file(output)
            r = t.start()
            self.assertTrue(r)
            r.complete()

            regex = r"\b()redo necessary because of invalid encoded path: 'a/\.\./'\n"
            self.assertRegex(output.getvalue(), regex)
            self.assertNotIn('a/../', rundb.get_fsobject_inputs(1, is_explicit_filter=False))

            self.assertFalse(t.start())

        with dlb.ex.Context():
            # add non-existent dependency with invalid memo
            rundb = dlb.ex._context._get_rundb()
            info_by_encoded_path = rundb.get_fsobject_inputs(1)
            info_by_encoded_path['d.h/'] = (False, marshal.dumps(42))
            rundb.update_dependencies_and_state(1, info_by_encoded_path=info_by_encoded_path)

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            regex = r"\b()redo necessary because of non-existent filesystem object: 'd\.h'\n"
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.start())


class RedoIfExplicitInputDependencyChangedChmodTest(testenv.TemporaryDirectoryWithChmodTestCase,
                                                    testenv.TemporaryWorkingDirectoryTestCase):

    def test_inaccessible_dependency_causes_redo(self):
        open('a.cpp', 'xb').close()
        open('a.h', 'xb').close()

        t = FTool(source_file='a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.start())
            self.assertTrue(t.start())  # because of new dependency
            self.assertFalse(t.start())

        os.mkdir('t')
        os.chmod('t', 0o000)

        try:
            with dlb.ex.Context():
                # add inaccessible dependency
                rundb = dlb.ex._context._get_rundb()
                info_by_encoded_path = rundb.get_fsobject_inputs(1)
                info_by_encoded_path['t/d.h/'] = (False, None)
                rundb.update_dependencies_and_state(1, info_by_encoded_path=info_by_encoded_path)

                output = io.StringIO()
                dlb.di.set_output_file(output)
                self.assertTrue(t.start())
                regex = r"\b()redo necessary because of inaccessible filesystem object: 't/d\.h'\n"
                self.assertRegex(output.getvalue(), regex)
                self.assertFalse(t.start())
        finally:
            os.chmod('t', 0o700)


class RedoIfDefinitionChangedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo_if_source_has_changed(self):

        with tempfile.TemporaryDirectory() as content_tmp_dir_path:
            open(os.path.join(content_tmp_dir_path, '__init__.py'), 'w').close()
            with open(os.path.join(content_tmp_dir_path, 'v.py'), 'w') as f:
                f.write(
                    'import dlb.ex\n'
                    'class A(dlb.ex.Tool):\n'
                    '    async def redo(self, result, context):\n'
                    '       pass'
                )

            zip_file_path = os.path.abspath('abc.zip')
            with zipfile.ZipFile(zip_file_path, 'w') as z:
                z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname='u4/__init__.py')
                z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname='u4/v.py')

        sys.path.insert(0, zip_file_path)
        try:
            # noinspection PyUnresolvedReferences
            import u4.v
        finally:
            del sys.path[0]

        t = u4.v.A()

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_threshold_level(dlb.di.DEBUG)
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            regex = r"\b()added 1 tool definition files as input dependency\n"
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.start())

        with zipfile.ZipFile(zip_file_path, 'w') as z:
            z.writestr('dummy', '')

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.start())
            regex = r"\b()redo necessary because of filesystem object: 'abc.zip' \n"
            self.assertRegex(output.getvalue(), regex)


class RedoRemovesObstructingExplicitOutputBeforeRedoTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_redo_ignores_nonexistent_output_file(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertTrue(t.start())
        self.assertFalse(os.path.exists('d'))

    def test_redo_does_not_remove_nonobstructing_outputs(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open('a.o', 'xb').close()
        os.mkdir('d/')

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertTrue(t.start())
        self.assertTrue(os.path.exists('a.o'))
        self.assertTrue(os.path.exists('d'))

    def test_redo_removes_obstructing_outputs(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()
        open('d', 'xb').close()
        os.mkdir('a.o')

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertTrue(t.start())
        self.assertTrue(os.path.isfile('a.o'))
        self.assertFalse(os.path.exists('d'))

    def test_run_without_redo_does_not_remove_output_files(self):
        os.mkdir('src')
        open(os.path.join('src', 'a.cpp'), 'xb').close()

        t = ATool(source_file='src/a.cpp', object_file='a.o', dummy_dir='d/')
        with dlb.ex.Context():
            self.assertTrue(t.start())

        os.mkdir('d')

        with dlb.ex.Context():
            self.assertFalse(t.start())

        self.assertTrue(os.path.isfile('a.o'))
        self.assertTrue(os.path.isdir('d'))
