# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.di
import dlb.cf
import dlb.ex
import dlb.ex._toolrun
import dlb.ex._dependaction
import os.path
import io
import asyncio
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class ConstructionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_noncontext(self):
        with dlb.ex.Context():
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                dlb.ex._toolrun.RedoContext('c', dict())

    def test_fails_for_none(self):
        with dlb.ex.Context() as c:
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                dlb.ex._toolrun.RedoContext(c, None)

    def test_fails_for_sequence(self):
        with dlb.ex.Context() as c:
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                dlb.ex._toolrun.RedoContext(c, ['a'])


class PrepareArgumentsTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_int_is_converted_to_str(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            arguments, cwd = rd.prepare_arguments([1])
        self.assertEqual(['1'], arguments)

    def test_path_is_converted_to_str(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            arguments, cwd = rd.prepare_arguments([dlb.fs.Path('src/a.c')])
        self.assertEqual([str(dlb.fs.Path('src/a.c').native)], arguments)

    def test_native_path_is_converted_to_str(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            arguments, cwd = rd.prepare_arguments([dlb.fs.Path('src/a.c').native])
        self.assertEqual([str(dlb.fs.Path('src/a.c').native)], arguments)

    def test_relative_path_is_relative_to_cwd(self):
        os.mkdir('src')
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            arguments, cwd = rd.prepare_arguments([dlb.fs.Path('src/a.c')], cwd='src/')
        self.assertEqual([str(dlb.fs.Path('a.c').native)], arguments)


@unittest.skipIf(not os.path.isfile('/bin/ls'), 'requires ls')
class ExecuteHelperTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_accepts_path_in_arguments(self):
        os.mkdir('-l')
        open(os.path.join('-l', 'content'), 'xb').close()
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper('ls', ['--full-time', dlb.fs.Path('-l')], stdout_output='stdout.txt')
            returncode = asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(0, returncode)
            regex = (
                r"(?m)\A"
                r".+ 0\n"
                r".+ .+ .+ .+ 0 .+ .+ .+ content\n\Z"
            )
            with open('stdout.txt', 'rb') as f:
                self.assertRegex(f.read().decode(), regex)

    def test_fails_for_directory_helper(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            with self.assertRaises(ValueError) as cm:
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls/', expected_returncodes=[1, 3]))
            msg = "cannot execute directory: 'ls/'"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_unexpected_return_code(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            with self.assertRaises(dlb.ex.HelperExecutionError) as cm:
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls', expected_returncodes=[1, 3]))
            msg = "execution of 'ls' returned unexpected exit code 0"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_open_file(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            with self.assertRaises(TypeError) as cm:
                with open('stdout.txt', 'xb') as f:
                    asyncio.get_event_loop().run_until_complete(
                        rd.execute_helper('ls', ['--full-time', dlb.fs.Path('-l')], stdout_output=f))
            msg = (
                "'path' must be a str, dlb.fs.Path or pathlib.PurePath object or a sequence, "
                "not <class '_io.BufferedWriter'>"
            )
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_pipe(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            with self.assertRaises(TypeError) as cm:
                asyncio.get_event_loop().run_until_complete(
                    rd.execute_helper('ls', ['--full-time', dlb.fs.Path('-l')], stdout_output=asyncio.subprocess.PIPE))
            msg = "'path' must be a str, dlb.fs.Path or pathlib.PurePath object or a sequence, not <class 'int'>"
            self.assertEqual(msg, str(cm.exception))

    def test_changes_cwd(self):
        os.mkdir('-l')
        open(os.path.join('-l', 'content'), 'xb').close()
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper('ls', ['-l'], cwd=dlb.fs.Path('-l'), stdout_output='stdout.txt')
            asyncio.get_event_loop().run_until_complete(e)
            regex = (
                r"(?m)\A"
                r".+ 0\n"
                r".+ .+ .+ .+ 0 .+ .+ .+ content\n\Z"
            )
            with open('stdout.txt', 'rb') as f:
                self.assertRegex(f.read().decode(), regex)

            e = rd.execute_helper('ls', ['-l'], cwd='.dlbroot/t', stdout_output='stdout2.txt')
            asyncio.get_event_loop().run_until_complete(e)
            regex = (
                r"(?m)\A"
                r".+ 0\n"
            )
            with open('stdout2.txt', 'rb') as f:
                self.assertRegex(f.read().decode(), regex)

    def test_fails_for_cwd_not_in_working_tree(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            with self.assertRaises(dlb.ex.WorkingTreePathError):
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls', cwd=dlb.fs.Path('..')))

    def test_fails_for_nonexistent_cwd(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls', cwd=dlb.fs.Path('ups')))
            self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

    def test_fails_for_uncollapsable_path_relative_to_cwd(self):
        os.mkdir('a')
        os.makedirs(os.path.join('x', 'y', 'b', 'c'))
        try:
            os.symlink(os.path.join('..', 'x', 'y', 'b'), os.path.join('a', 'b'), target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            asyncio.get_event_loop().run_until_complete(rd.execute_helper(
                'ls', [dlb.fs.Path('a/b')], cwd=dlb.fs.Path('a/b/c'), stdout_output=NotImplemented))  # 'a/b/..'
            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                asyncio.get_event_loop().run_until_complete(rd.execute_helper(
                    'ls', [dlb.fs.Path('a/b'), dlb.fs.Path('a')], cwd=dlb.fs.Path('a/b/c')))  # 'a/b/../..'
            p = os.path.join(os.getcwd(), 'a', 'b')
            msg = f"not a collapsable path, since this is a symbolic link: {p!r}"
            self.assertEqual(msg, str(cm.exception))

    def test_relative_paths_are_replaced(self):
        os.makedirs(os.path.join('a', 'b', 'c'))
        os.mkdir(os.path.join('a', 'x'))

        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper(
                'ls', ['-d', dlb.fs.Path('.'), dlb.fs.Path('a/x'), dlb.fs.Path('.dlbroot/t/')],
                cwd=dlb.fs.Path('a/b/c'), stdout_output='stdout.txt')
            asyncio.get_event_loop().run_until_complete(e)
            output = (
                "../../..\n"
                "../../../.dlbroot/t\n"
                "../../x\n"
            )
            with open('stdout.txt', 'rb') as f:
                self.assertEqual(output, f.read().decode())

    def test_fails_for_relative_path_not_in_working_tree(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper('ls', [dlb.fs.Path('..')])
            with self.assertRaises(dlb.ex.WorkingTreePathError):
                asyncio.get_event_loop().run_until_complete(e)

    def test_can_write_to_open_file(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper('ls', ['-l'], stdout_output='stdout.txt')
            asyncio.get_event_loop().run_until_complete(e)
            with open('stdout.txt', 'rb') as f:
                self.assertIn(b'\n', f.read())

    def test_can_write_to_devnull(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper('ls', ['ls --unsupported-option '], stderr_output=NotImplemented,
                                  expected_returncodes=[2])
            asyncio.get_event_loop().run_until_complete(e)

    def test_informs(self):
        orig = dlb.cf.level.helper_execution

        try:
            dlb.cf.level.helper_execution = dlb.di.INFO

            with dlb.ex.Context() as c:
                rd = dlb.ex._toolrun.RedoContext(c, dict())
                e = rd.execute_helper('ls', ['-l'], stdout_output=NotImplemented)

                output = io.StringIO()
                dlb.di.set_output_file(output)
                asyncio.get_event_loop().run_until_complete(e)

            msg = (
                "I execute helper 'ls' \n" 
                "  | path:        '/bin/ls' \n" 
                "  | arguments:   '-l' \n"
                "  | directory:   './' \n"
                "  | environment: {}\n"
            )
            self.assertEqual(msg, output.getvalue())

        finally:
            dlb.cf.level.helper_execution = orig


@unittest.skipIf(not os.path.isfile('/bin/sh'), 'requires sh')
class ExecuteHelperEnvVarTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_can_override_envvar(self):
        with dlb.ex.Context() as c:
            c.env.import_from_outer('X', pattern='.*', example='')
            c.env.import_from_outer('Y', pattern='.*', example='')
            c.env['X'] = 'x'
            c.env['Y'] = 'z'
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper('sh', ['-c', 'echo $X-$Y'], forced_env={'Y': 'zzz...'}, stdout_output='stdout.txt')
            _ = asyncio.get_event_loop().run_until_complete(e)
            with open('stdout.txt', 'rb') as f:
                self.assertEqual(b'x-zzz...', f.read().strip())


@unittest.skipIf(not os.path.isfile('/bin/sh'), 'requires sh')
class ExecuteHelperWithOutputTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_returns_output_as_bytes_without_processor(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())

            e = rd.execute_helper_with_output('sh', ['-c', 'echo 1_; echo 2_ >&2; echo 3'],
                                              output_to_process=1, other_output=NotImplemented)
            r, output = asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(0, r)
            self.assertEqual(b'1_\n3\n', output)

            e = rd.execute_helper_with_output('sh', ['-c', 'echo 1_; echo 2_ >&2; echo 3'],
                                              output_to_process=2, other_output=NotImplemented)
            r, output = asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(0, r)
            self.assertEqual(b'2_\n', output)

    def test_can_write_to_file(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper_with_output('sh', ['-c', 'echo 1_; echo 2_ >&2; echo 3'],
                                              output_to_process=1, other_output='stderr.txt')
            r, output = asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(0, r)
            self.assertEqual(b'1_\n3\n', output)
            with open('stderr.txt', 'rb') as f:
                self.assertEqual(b'2_\n', f.read())

    def test_return_processor_result_with_processor(self):
        with dlb.ex.Context() as c:
            class ChunkProcessor(dlb.ex._toolrun.ChunkProcessor):
                separator = b'_'

                def __init__(self):
                    self.chunks = []

                def process(self, chunk: bytes, is_last: bool):
                    self.chunks.append((chunk, is_last))

                @property
                def result(self):
                    return self.chunks

            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper_with_output('sh', ['-c', 'echo 1_; echo 2_; echo 3'],
                                              output_to_process=1, chunk_processor=ChunkProcessor())
            r, output = asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(0, r)
            self.assertEqual([(b'1', False), (b'\n2', False), (b'\n3\n', True)], output)

    def test_processor_can_abort(self):
        with dlb.ex.Context() as c:
            class ChunkProcessor(dlb.ex._toolrun.ChunkProcessor):
                def __init__(self):
                    self.n = 0

                def process(self, chunk: bytes, is_last: bool):
                    self.n += 1
                    if self.n > 1000:
                        raise ValueError("it's enough!")

                @property
                def result(self):
                    return self.n

            rd = dlb.ex._toolrun.RedoContext(c, dict())
            e = rd.execute_helper_with_output('sh', ['-c', 'yes'], output_to_process=1,
                                              chunk_processor=ChunkProcessor())
            with self.assertRaises(ValueError) as cm:
                asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual("it's enough!", str(cm.exception))

    def test_aborts_for_too_large_chunk_with_processor(self):
        with dlb.ex.Context() as c:
            class ChunkProcessor(dlb.ex._toolrun.ChunkProcessor):
                def __init__(self):
                    self.chunks = []

                def process(self, chunk: bytes, is_last: bool):
                    self.chunks.append((chunk, is_last))

                @property
                def result(self):
                    return self.chunks

            rd = dlb.ex._toolrun.RedoContext(c, dict())
            processor = ChunkProcessor()
            processor.max_chunk_size = 20
            e = rd.execute_helper_with_output('sh', ['-c', 'echo 1; echo 01234567890123456789'],
                                              output_to_process=1, chunk_processor=processor)
            asyncio.get_event_loop().run_until_complete(e)

            processor = ChunkProcessor()
            processor.max_chunk_size = 19
            e = rd.execute_helper_with_output('sh', ['-c', 'echo 1; echo 01234567890123456789'],
                                              output_to_process=1, chunk_processor=processor)
            with self.assertRaises(asyncio.LimitOverrunError):
                asyncio.get_event_loop().run_until_complete(e)

    def test_fails_for_invalid_output_to_process(self):
        msg = "'output_to_process' must be 1 or 2"

        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())

            e = rd.execute_helper_with_output('sh', ['-c', 'echo'], output_to_process=0)
            with self.assertRaises(ValueError) as cm:
                asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(msg, str(cm.exception))

            # noinspection PyTypeChecker
            e = rd.execute_helper_with_output('sh', ['-c', 'echo'], output_to_process='0')
            with self.assertRaises(ValueError) as cm:
                asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_invalid_chunk_processor(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())

            # noinspection PyTypeChecker
            e = rd.execute_helper_with_output('sh', ['-c', 'echo'], chunk_processor=1)
            with self.assertRaises(TypeError) as cm:
                asyncio.get_event_loop().run_until_complete(e)
            msg = "'chunk_processor' must be None or a ChunkProcessor object, not <class 'int'>"
            self.assertEqual(msg, str(cm.exception))

            e = rd.execute_helper_with_output('sh', ['-c', 'echo'], chunk_processor=dlb.ex._toolrun.ChunkProcessor())
            with self.assertRaises(NotImplementedError):
                asyncio.get_event_loop().run_until_complete(e)

            # noinspection PyAbstractClass
            class ChunkProcessor(dlb.ex._toolrun.ChunkProcessor):
                def process(self, chunk: bytes, is_last: bool):
                    pass

            ChunkProcessor.separator = '\n'
            e = rd.execute_helper_with_output('sh', ['-c', 'echo'], chunk_processor=ChunkProcessor())
            with self.assertRaises(TypeError) as cm:
                asyncio.get_event_loop().run_until_complete(e)
            msg = "'chunk_processor.separator' must be bytes object, not <class 'str'>"
            self.assertEqual(msg, str(cm.exception))

            ChunkProcessor.separator = b''
            e = rd.execute_helper_with_output('sh', ['-c', 'echo'], chunk_processor=ChunkProcessor())
            with self.assertRaises(ValueError) as cm:
                asyncio.get_event_loop().run_until_complete(e)
            msg = "'chunk_processor.separator' must not be empty"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_invalid_other_output(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())

            e = rd.execute_helper_with_output('sh', ['-c', 'echo'], other_output=1)
            with self.assertRaises(TypeError) as cm:
                asyncio.get_event_loop().run_until_complete(e)
            msg = "'path' must be a str, dlb.fs.Path or pathlib.PurePath object or a sequence, not <class 'int'>"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_unexpected_return_code(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            with self.assertRaises(dlb.ex.HelperExecutionError) as cm:
                e = rd.execute_helper_with_output('sh', ['-c', 'echo'], other_output=NotImplemented,
                                                  expected_returncodes=[1])
                asyncio.get_event_loop().run_until_complete(e)
            msg = "execution of 'sh' returned unexpected exit code 0"
            self.assertEqual(msg, str(cm.exception))


@unittest.skipIf(not os.path.isfile('/bin/ls'), 'requires ls')
class ExecuteHelperRawTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_works_with_all_arguments(self):
        async def redo(context):
            proc = await context.execute_helper_raw(
                'ls', ['--unsupported-option '],
                cwd=None, forced_env=None,
                stdin=None, stdout=None, stderr=asyncio.subprocess.DEVNULL, limit=1024)
            await proc.communicate()
            return proc

        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            proc = asyncio.get_event_loop().run_until_complete(redo(rd))
            self.assertIsInstance(proc, asyncio.subprocess.Process)
            self.assertEqual(2, proc.returncode)

    def test_fails_for_byteio(self):
        async def redo(context):
            f = io.BytesIO()
            proc = await context.execute_helper_raw(
                'ls', ['--unsupported-option '],
                cwd=None, forced_env=None,
                stdin=None, stdout=None, stderr=f, limit=1024)
            await proc.communicate()
            return proc

        with dlb.ex.Context() as c:
            rd = dlb.ex._toolrun.RedoContext(c, dict())
            with self.assertRaises(io.UnsupportedOperation) as cm:
                asyncio.get_event_loop().run_until_complete(redo(rd))
            self.assertEqual('fileno', cm.exception.args[0])


class ReplaceOutputTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_nonoutput_dependency(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.RegularFileOutputAction(dlb.ex.output.RegularFile(), 'test_file')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a/b'): action})

            with self.assertRaises(ValueError) as cm:
                rd.replace_output('a/b/', 'c')
            msg = "path is not contained in any explicit output dependency: 'a/b/'"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_isdir_discrepancy(self):
        with dlb.ex.Context() as c:
            file_action = dlb.ex._dependaction.RegularFileOutputAction(
                dlb.ex.output.RegularFile(), 'test_file')
            directory_action = dlb.ex._dependaction.RegularFileOutputAction(
                dlb.ex.output.Directory(), 'test_directory')
            rd = dlb.ex._toolrun.RedoContext(c, {
                dlb.fs.Path('a/b'): file_action,
                dlb.fs.Path('c/'): directory_action
            })

            with self.assertRaises(ValueError) as cm:
                rd.replace_output('a/b', 'c/')
            msg = "cannot replace non-directory by directory: 'a/b'"
            self.assertEqual(msg, str(cm.exception))

            with self.assertRaises(ValueError) as cm:
                rd.replace_output('c/', 'a/b')
            msg = "cannot replace directory by non-directory: 'c/'"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_if_source_does_not_exist(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.RegularFileOutputAction(dlb.ex.output.RegularFile(), 'test_file')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a/b'): action})

            with self.assertRaises(ValueError) as cm:
                rd.replace_output('a/b', dlb.fs.Path('a/b'))
            regex = (
                r"(?m)\A"
                r"'source' is not a permitted working tree path of an existing filesystem object: 'a/b'\n"
                r"  \| reason: .*\Z"
            )
            self.assertRegex(str(cm.exception), regex)

    def test_fails_if_source_is_destination(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.RegularFileOutputAction(dlb.ex.output.RegularFile(), 'test_file')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a/b'): action})

            os.mkdir('a')
            open(os.path.join('a', 'b'), 'wb').close()

            with self.assertRaises(ValueError) as cm:
                rd.replace_output('a/b', dlb.fs.Path('a/b'))
            msg = "cannot replace a path by itself: 'a/b'"
            self.assertEqual(msg, str(cm.exception))


class ReplaceRegularFileOutputTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_replaces_if_different_size(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.RegularFileOutputAction(
                dlb.ex.output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a'): action})

            with open('a', 'wb') as f:
                f.write(b'A')
            with open('b', 'wb') as f:
                f.write(b'BB')

            output = io.StringIO()
            dlb.di.set_output_file(output)
            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            with open('a', 'rb') as f:
                self.assertEqual(b'BB', f.read())

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)
            self.assertEqual("I replaced regular file with different one: 'a'\n", output.getvalue())

    def test_replaces_if_different_content_of_same_size(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.RegularFileOutputAction(
                dlb.ex.output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a'): action})

            with open('a', 'wb') as f:
                f.write(b'AA')
            with open('b', 'wb') as f:
                f.write(b'BB')

            output = io.StringIO()
            dlb.di.set_output_file(output)
            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            with open('a', 'rb') as f:
                self.assertEqual(b'BB', f.read())

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)
            self.assertEqual("I replaced regular file with different one: 'a'\n", output.getvalue())

    def test_replaces_if_nonexistent(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.RegularFileOutputAction(
                dlb.ex.output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a'): action})

            with open('b', 'wb') as f:
                f.write(b'BB')

            output = io.StringIO()
            dlb.di.set_output_file(output)
            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            with open('a', 'rb') as f:
                self.assertEqual(b'BB', f.read())

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)
            self.assertEqual("I replaced regular file with different one: 'a'\n", output.getvalue())

    def test_creates_nonexistent_destination_directory(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.RegularFileOutputAction(
                dlb.ex.output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('x/y/a'): action})

            with open('b', 'wb') as f:
                f.write(b'BB')

            output = io.StringIO()
            dlb.di.set_output_file(output)
            rd.replace_output('x/y/a', 'b')

            with open('x/y/a', 'rb') as f:
                self.assertEqual(b'BB', f.read())

    def test_does_not_replace_if_same_content(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.RegularFileOutputAction(
                dlb.ex.output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a'): action})

            with open('a', 'wb') as f:
                f.write(b'AA')
            with open('b', 'wb') as f:
                f.write(b'AA')

            output = io.StringIO()
            dlb.di.set_output_file(output)
            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            self.assertNotIn(dlb.fs.Path('a'), rd.modified_outputs)
            self.assertEqual("I kept regular file because replacement has same content: 'a'\n", output.getvalue())


class ReplaceDirectoryOutputTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_replaces_nonempty(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.DirectoryOutputAction(dlb.ex.output.Directory(), 'test_directory')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a/'): action})

            os.makedirs('a/b/c')
            os.makedirs('u/v')

            output = io.StringIO()
            dlb.di.set_output_file(output)
            rd.replace_output('a/', 'u/')

            self.assertFalse(os.path.exists('b'))
            self.assertTrue(os.path.exists(os.path.join('a', 'v')))

            self.assertIn(dlb.fs.Path('a/'), rd.modified_outputs)
            self.assertEqual("I replaced directory: 'a/'\n", output.getvalue())

    def test_creates_nonexistent_destination_directory(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.DirectoryOutputAction(dlb.ex.output.Directory(), 'test_directory')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('x/y/a/'): action})

            output = io.StringIO()
            dlb.di.set_output_file(output)
            os.makedirs('u/v')

            rd.replace_output('x/y/a/', 'u/')
            self.assertTrue(os.path.exists(os.path.join('x', 'y', 'a', 'v')))


class ReplaceNonRegularFileOutputTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_replaces_symlink(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.NonRegularFileOutputAction(dlb.ex.output.NonRegularFile(), 'test')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('a'): action})

            try:
                os.symlink('/x/y', 'a')
                os.symlink('/u/v', 'b')
            except OSError:  # on platform or filesystem that does not support symlinks
                self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
                raise unittest.SkipTest from None

            output = io.StringIO()
            dlb.di.set_output_file(output)
            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            self.assertEqual('/u/v', os.readlink('a'))

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)
            self.assertEqual("I replaced non-regular file: 'a'\n", output.getvalue())

    def test_creates_nonexistent_destination_directory(self):
        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.NonRegularFileOutputAction(dlb.ex.output.NonRegularFile(), 'test')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('x/y/a'): action})

            try:
                os.symlink('/u/v', 'b')
            except OSError:  # on platform or filesystem that does not support symlinks
                self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
                raise unittest.SkipTest from None

            output = io.StringIO()
            dlb.di.set_output_file(output)
            rd.replace_output('x/y/a', 'b')

            self.assertEqual('/u/v', os.readlink(os.path.join('x', 'y', 'a')))
