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


class FindPathInParameterTest(unittest.TestCase):

    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.Context().find_path_in('/a', [])
        self.assertEqual("'path' must not be absolute", str(cm.exception))

    def test_fails_for_str_or_bytes(self):
        msg = "'search_prefixes' must be iterable (other than 'str' or 'bytes')"

        with self.assertRaises(TypeError) as cm:
            dlb.ex.Context().find_path_in('a', 'abc')
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.ex.Context().find_path_in('a', b'abc')
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_non_directory(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.Context().find_path_in('a', [dlb.fs.Path('/x')])
        self.assertEqual("not a directory: '/x'", str(cm.exception))

    def test_none_for_empty(self):
        self.assertIsNone(dlb.ex.Context().find_path_in('a', []))

    def test_none_if_not_found(self):
        self.assertFalse(os.path.exists('/not/existing/path'))
        self.assertIsNone(dlb.ex.Context().find_path_in('a', ['/not/existing/path/']))


class FindPathInTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_finds_first(self):
        os.mkdir('.dlbroot')
        os.makedirs('d/a/b')
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('a/b/', ['c/', 'd/', 'e/'])
            self.assertEqual(dlb.ex.Context.root_path / 'd/a/b/', p)

    def test_makes_relative_to_working_tree_root(self):
        os.mkdir('.dlbroot')
        os.mkdir('x')
        os.makedirs('d/a/b')
        with dlb.ex.Context():
            with tools_for_test.DirectoryChanger('x'):
                p = dlb.ex.Context().find_path_in('a/b/', ['d/'])
            self.assertEqual(dlb.ex.Context.root_path / 'd/a/b/', p)

    def test_finds_only_directory_for_directory(self):
        os.mkdir('.dlbroot')
        os.makedirs('d/')
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('d/', ['.'])
            self.assertEqual(dlb.ex.Context.root_path / 'd/', p)
            p = dlb.ex.Context().find_path_in('d', ['.'])
            self.assertIsNone(p)

    def test_finds_only_nondirectory_for_nondirectory(self):
        os.mkdir('.dlbroot')
        with open('d', 'xb'):
            pass
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('d', ['.'])
            self.assertEqual(dlb.ex.Context.root_path / 'd', p)
            p = dlb.ex.Context().find_path_in('d/', ['.'])
            self.assertIsNone(p)
