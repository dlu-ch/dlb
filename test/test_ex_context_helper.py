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


class BinarySearchPathTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_if_not_running(self):
        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex.NotRunningError):
            c.binary_search_paths

    def test_is_nonempty_tuple_of_absolute_paths(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context():
            paths = dlb.ex.Context.binary_search_paths

        self.assertIsInstance(paths, tuple)
        self.assertGreater(len(paths), 0)
        for p in paths:
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(p.is_absolute())

        self.assertEqual(len(set(paths)), len(paths))
