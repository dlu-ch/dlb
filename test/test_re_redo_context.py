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
import unittest
import tools_for_test


class RedoContextTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_read_access_to_inactive_context_is_possible(self):
        os.mkdir('.dlbroot')
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
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c:
            c.helper['a'] = '/a'
            rc = dlb.ex.RedoContext(c)
            with self.assertRaises(TypeError):
                rc.helper['a'] = '/A'
            with self.assertRaises(TypeError):
                rc.env['a'] = '/A'

    def test_fails_without_active_context(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c:
            pass
        with self.assertRaises(dlb.ex.NotRunningError):
            dlb.ex.RedoContext(c)

    def test_fails_for_redo_context(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c:
            rc = dlb.ex.RedoContext(c)
            with self.assertRaises(TypeError) as cm:
                rc = dlb.ex.RedoContext(rc)
            self.assertEqual("'context' must be a Context object", str(cm.exception))
