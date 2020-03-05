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
import asyncio
import unittest
import tools_for_test


class AccessTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_read_access_to_inactive_context_is_possible(self):
        with dlb.ex.Context():
            with dlb.ex.Context() as c1:
                c1.helper['a'] = '/a'
                with dlb.ex.Context() as c2:
                    c2.helper['b'] = '/b'
                    rc1 = dlb.ex.RedoContext(c1)
                    rc2 = dlb.ex.RedoContext(c2)
                    self.assertEqual(dlb.fs.Path('/a'), rc1.helper['a'])
                    self.assertEqual(dlb.fs.Path('/b'), rc2.helper['b'])
                self.assertEqual(dlb.fs.Path('/a'), rc1.helper['a'])
                self.assertEqual(dlb.fs.Path('/b'), rc2.helper['b'])
            self.assertEqual(dlb.fs.Path('/a'), rc1.helper['a'])
            self.assertEqual(dlb.fs.Path('/b'), rc2.helper['b'])

    def test_write_access_to_inactive_context_fails(self):
        with dlb.ex.Context() as c:
            c.helper['a'] = '/a'
            rc = dlb.ex.RedoContext(c)
            with self.assertRaises(TypeError):
                rc.helper['a'] = '/A'
            with self.assertRaises(TypeError):
                rc.env['a'] = '/A'

    def test_fails_without_active_context(self):
        with dlb.ex.Context() as c:
            pass
        with self.assertRaises(dlb.ex.NotRunningError):
            dlb.ex.RedoContext(c)

    def test_fails_for_redo_context(self):
        with dlb.ex.Context() as c:
            rc = dlb.ex.RedoContext(c)
            with self.assertRaises(TypeError) as cm:
                # noinspection PyTypeChecker
                dlb.ex.RedoContext(rc)
            self.assertEqual("'context' must be a Context object", str(cm.exception))


class ExecuteHelperTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_accepts_path_in_arguments(self):
        os.mkdir('-l')
        with open(os.path.join('-l', 'content'), 'xb'):
            pass
        with dlb.ex.Context(find_helpers=True) as c:
            rd = dlb.ex.RedoContext(c)
            e = rd.execute_helper('ls', ['--full-time', dlb.fs.Path('-l')], stdout=asyncio.subprocess.PIPE)
            returncode, stdout, stderr = asyncio.get_event_loop().run_until_complete(e)
            self.assertEqual(0, returncode)
            regex = (
                r"(?m)\A"
                r".+ 0\n"
                r".+ .+ .+ .+ 0 .+ .+ .+ content\n\Z"
            )
            self.assertRegex(stdout.decode(), regex)

    def test_fails_for_unexpected_return_code(self):
        with dlb.ex.Context(find_helpers=True) as c:
            rd = dlb.ex.RedoContext(c)
            with self.assertRaises(dlb.ex.HelperExecutionError) as cm:
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls', expected_returncodes=[1, 3]))
            msg = f"execution of 'ls' returned unexpected exit code 0"
            self.assertEqual(msg, str(cm.exception))

    def test_changes_cwd(self):
        os.mkdir('-l')
        with open(os.path.join('-l', 'content'), 'xb'):
            pass
        with dlb.ex.Context(find_helpers=True) as c:
            rd = dlb.ex.RedoContext(c)
            e = rd.execute_helper('ls', ['-l'], cwd=dlb.fs.Path('-l'), stdout=asyncio.subprocess.PIPE)
            returncode, stdout, stderr = asyncio.get_event_loop().run_until_complete(e)
            regex = (
                r"(?m)\A"
                r".+ 0\n"
                r".+ .+ .+ .+ 0 .+ .+ .+ content\n\Z"
            )
            self.assertRegex(stdout.decode(), regex)

    def test_fails_for_cwd_not_in_managed_tree(self):
        with dlb.ex.Context(find_helpers=True) as c:
            rd = dlb.ex.RedoContext(c)
            with self.assertRaises(dlb.fs.manip.PathNormalizationError):
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls', cwd=dlb.fs.Path('..')))

    def test_fails_for_nonexistent_cwd(self):
        with dlb.ex.Context(find_helpers=True) as c:
            rd = dlb.ex.RedoContext(c)
            with self.assertRaises(dlb.fs.manip.PathNormalizationError) as cm:
                asyncio.get_event_loop().run_until_complete(rd.execute_helper('ls', cwd=dlb.fs.Path('ups')))
            self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

    def test_relative_paths_are_replaced(self):
        os.makedirs(os.path.join('a', 'b', 'c'))
        os.mkdir(os.path.join('a', 'x'))

        with dlb.ex.Context(find_helpers=True) as c:
            rd = dlb.ex.RedoContext(c)
            e = rd.execute_helper(
                'ls', ['-d', dlb.fs.Path('.'), dlb.fs.Path('a/x')],
                cwd=dlb.fs.Path('a/b/c'),
                stdout=asyncio.subprocess.PIPE)
            returncode, stdout, stderr = asyncio.get_event_loop().run_until_complete(e)
            output = (
                "../../..\n"
                "../../x\n"
            )
            self.assertRegex(output, stdout.decode())

    def test_fails_for_relative_path_not_in_managed_tree(self):
        with dlb.ex.Context(find_helpers=True) as c:
            rd = dlb.ex.RedoContext(c)
            e = rd.execute_helper('ls', [dlb.fs.Path('..')])
            with self.assertRaises(dlb.fs.manip.PathNormalizationError):
                asyncio.get_event_loop().run_until_complete(e)
