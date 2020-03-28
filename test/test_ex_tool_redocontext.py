# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex
import dlb.ex.dependaction
import asyncio
import unittest
import tools_for_test


class ConstructionTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_noncontext(self):
        with dlb.ex.Context():
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                dlb.ex.tool._RedoContext('c', dict())

    def test_fails_for_none(self):
        with dlb.ex.Context() as c:
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                dlb.ex.tool._RedoContext(c, None)

    def test_fails_for_sequence(self):
        with dlb.ex.Context() as c:
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                dlb.ex.tool._RedoContext(c, ['a'])


@unittest.skipIf(not os.path.isfile('/bin/ls'), 'requires ls')
class ExecuteHelperTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_accepts_path_in_arguments(self):
        os.mkdir('-l')
        open(os.path.join('-l', 'content'), 'xb').close()
        with dlb.ex.Context() as c:
            rd = dlb.ex.tool._RedoContext(c, dict())
            e = rd.execute_helper('ls', ['--full-time', dlb.fs.Path('-l')], stdout=asyncio.subprocess.PIPE)
            returncode, stdout, stderr = asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(0, returncode)
            regex = (
                r"(?m)\A"
                r".+ 0\n"
                r".+ .+ .+ .+ 0 .+ .+ .+ content\n\Z"
            )
            self.assertRegex(stdout.decode(), regex)

    def test_fails_for_directory_helper(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex.tool._RedoContext(c, dict())
            with self.assertRaises(ValueError) as cm:
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls/', expected_returncodes=[1, 3]))
            msg = "cannot execute directory: 'ls/'"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_unexpected_return_code(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex.tool._RedoContext(c, dict())
            with self.assertRaises(dlb.ex.HelperExecutionError) as cm:
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls', expected_returncodes=[1, 3]))
            msg = "execution of 'ls' returned unexpected exit code 0"
            self.assertEqual(msg, str(cm.exception))

    def test_changes_cwd(self):
        os.mkdir('-l')
        open(os.path.join('-l', 'content'), 'xb').close()
        with dlb.ex.Context() as c:
            rd = dlb.ex.tool._RedoContext(c, dict())
            e = rd.execute_helper('ls', ['-l'], cwd=dlb.fs.Path('-l'), stdout=asyncio.subprocess.PIPE)
            returncode, stdout, stderr = asyncio.get_event_loop().run_until_complete(e)
            regex = (
                r"(?m)\A"
                r".+ 0\n"
                r".+ .+ .+ .+ 0 .+ .+ .+ content\n\Z"
            )
            self.assertRegex(stdout.decode(), regex)

            e = rd.execute_helper('ls', ['-l'], cwd='.dlbroot/t', stdout=asyncio.subprocess.PIPE)
            returncode, stdout, stderr = asyncio.get_event_loop().run_until_complete(e)
            regex = (
                r"(?m)\A"
                r".+ 0\n"
            )
            self.assertRegex(stdout.decode(), regex)

    def test_fails_for_cwd_not_in_working_tree(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex.tool._RedoContext(c, dict())
            with self.assertRaises(dlb.ex.WorkingTreePathError):
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls', cwd=dlb.fs.Path('..')))

    def test_fails_for_nonexistent_cwd(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex.tool._RedoContext(c, dict())
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
            rd = dlb.ex.tool._RedoContext(c, dict())
            asyncio.get_event_loop().run_until_complete(rd.execute_helper(
                'ls', [dlb.fs.Path('a/b')], cwd=dlb.fs.Path('a/b/c')))  # 'a/b/..'
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
            rd = dlb.ex.tool._RedoContext(c, dict())
            e = rd.execute_helper(
                'ls', ['-d', dlb.fs.Path('.'), dlb.fs.Path('a/x'), dlb.fs.Path('.dlbroot/t/')],
                cwd=dlb.fs.Path('a/b/c'),
                stdout=asyncio.subprocess.PIPE)
            returncode, stdout, stderr = asyncio.get_event_loop().run_until_complete(e)
            output = (
                "../../..\n"
                "../../../.dlbroot/t\n"
                "../../x\n"
            )
            self.assertRegex(output, stdout.decode())

    def test_fails_for_relative_path_not_in_working_tree(self):
        with dlb.ex.Context() as c:
            rd = dlb.ex.tool._RedoContext(c, dict())
            e = rd.execute_helper('ls', [dlb.fs.Path('..')])
            with self.assertRaises(dlb.ex.WorkingTreePathError):
                asyncio.get_event_loop().run_until_complete(e)


@unittest.skipIf(not os.path.isfile('/bin/sh'), 'requires sh')
class ExecuteHelperEnvVarTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_can_override_envvar(self):
        with dlb.ex.Context() as c:
            c.env.import_from_outer('X', restriction='.*', example='')
            c.env.import_from_outer('Y', restriction='.*', example='')
            c.env['X'] = 'x'
            c.env['Y'] = 'z'
            rd = dlb.ex.tool._RedoContext(c, dict())
            e = rd.execute_helper('sh', ['-c', 'echo $X-$Y'], forced_env={'Y': 'zzz...'},
                                  stdout=asyncio.subprocess.PIPE)
            _, stdout, _ = asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual('x-zzz...', stdout.decode().strip())


class ReplaceOutputTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_nonoutput_dependency(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.RegularFileOutputAction(dlb.ex.Tool.Output.RegularFile(), 'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a/b'): action})

            with self.assertRaises(ValueError) as cm:
                rd.replace_output('a/b/', 'c')
            msg = "path is not contained in any explicit output dependency: 'a/b/'"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_isdir_discrepancy(self):
        with dlb.ex.Context() as c:
            file_action = dlb.ex.dependaction.RegularFileOutputAction(
                dlb.ex.Tool.Output.RegularFile(), 'test_file')
            directory_action = dlb.ex.dependaction.RegularFileOutputAction(
                dlb.ex.Tool.Output.Directory(), 'test_directory')
            rd = dlb.ex.tool._RedoContext(c, {
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
            action = dlb.ex.dependaction.RegularFileOutputAction(dlb.ex.Tool.Output.RegularFile(), 'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a/b'): action})

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
            action = dlb.ex.dependaction.RegularFileOutputAction(dlb.ex.Tool.Output.RegularFile(), 'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a/b'): action})

            os.mkdir('a')
            open(os.path.join('a', 'b'), 'wb').close()

            with self.assertRaises(ValueError) as cm:
                rd.replace_output('a/b', dlb.fs.Path('a/b'))
            msg = "cannot replace a path by itself: 'a/b'"
            self.assertEqual(msg, str(cm.exception))


class ReplaceRegularFileOutputTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_replaces(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.RegularFileOutputAction(dlb.ex.Tool.Output.RegularFile(), 'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a'): action})

            with open('a', 'wb') as f:
                f.write(b'A')
            with open('b', 'wb') as f:
                f.write(b'B')

            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            with open('a', 'rb') as f:
                self.assertEqual(b'B', f.read())

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)

    def test_replaces_if_different_size(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.RegularFileOutputAction(
                dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a'): action})

            with open('a', 'wb') as f:
                f.write(b'A')
            with open('b', 'wb') as f:
                f.write(b'BB')

            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            with open('a', 'rb') as f:
                self.assertEqual(b'BB', f.read())

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)

    def test_replaces_if_different_content_of_same_size(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.RegularFileOutputAction(
                dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a'): action})

            with open('a', 'wb') as f:
                f.write(b'AA')
            with open('b', 'wb') as f:
                f.write(b'BB')

            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            with open('a', 'rb') as f:
                self.assertEqual(b'BB', f.read())

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)

    def test_replaces_if_nonexistent(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.RegularFileOutputAction(
                dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a'): action})

            with open('b', 'wb') as f:
                f.write(b'BB')

            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            with open('a', 'rb') as f:
                self.assertEqual(b'BB', f.read())

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)

    def test_creates_nonexistent_destination_directory(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.RegularFileOutputAction(
                dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('x/y/a'): action})

            with open('b', 'wb') as f:
                f.write(b'BB')

            rd.replace_output('x/y/a', 'b')

            with open('x/y/a', 'rb') as f:
                self.assertEqual(b'BB', f.read())

    def test_does_not_replace__if_same_content(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.RegularFileOutputAction(
                dlb.ex.Tool.Output.RegularFile(replace_by_same_content=False),
                'test_file')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a'): action})

            with open('a', 'wb') as f:
                f.write(b'AA')
            with open('b', 'wb') as f:
                f.write(b'AA')

            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            self.assertNotIn(dlb.fs.Path('a'), rd.modified_outputs)


class ReplaceDirectoryOutputTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_replaces_nonempty(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.DirectoryOutputAction(dlb.ex.Tool.Output.Directory(), 'test_directory')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a/'): action})

            os.makedirs('a/b/c')
            os.makedirs('u/v')

            rd.replace_output('a/', 'u/')

            self.assertFalse(os.path.exists('b'))
            self.assertTrue(os.path.exists(os.path.join('a', 'v')))

            self.assertIn(dlb.fs.Path('a/'), rd.modified_outputs)

    def test_creates_nonexistent_destination_directory(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.DirectoryOutputAction(dlb.ex.Tool.Output.Directory(), 'test_directory')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('x/y/a/'): action})

            os.makedirs('u/v')

            rd.replace_output('x/y/a/', 'u/')
            self.assertTrue(os.path.exists(os.path.join('x', 'y', 'a', 'v')))


class ReplaceNonRegularFileOutputTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_replaces_symlink(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.NonRegularFileOutputAction(dlb.ex.Tool.Output.NonRegularFile(), 'test')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('a'): action})

            try:
                os.symlink('/x/y', 'a')
                os.symlink('/u/v', 'b')
            except OSError:  # on platform or filesystem that does not support symlinks
                self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
                raise unittest.SkipTest from None

            rd.replace_output('a', 'b')

            self.assertFalse(os.path.exists('b'))
            self.assertEqual('/u/v', os.readlink('a'))

            self.assertIn(dlb.fs.Path('a'), rd.modified_outputs)

    def test_creates_nonexistent_destination_directory(self):
        with dlb.ex.Context() as c:
            action = dlb.ex.dependaction.NonRegularFileOutputAction(dlb.ex.Tool.Output.NonRegularFile(), 'test')
            rd = dlb.ex.tool._RedoContext(c, {dlb.fs.Path('x/y/a'): action})

            try:
                os.symlink('/u/v', 'b')
            except OSError:  # on platform or filesystem that does not support symlinks
                self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
                raise unittest.SkipTest from None

            rd.replace_output('x/y/a', 'b')
            self.assertEqual('/u/v', os.readlink(os.path.join('x', 'y', 'a')))
