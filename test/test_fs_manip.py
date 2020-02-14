# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.fs.manip
import pathlib
import tempfile
import collections
import unittest
import tools_for_test


class RemoveFilesystemObject(tools_for_test.TemporaryDirectoryTestCase):

    @staticmethod
    def create_dir_a_in_cwd(all_writable=True):
        os.makedirs(os.path.join('a', 'b1', 'c', 'd1'))
        os.makedirs(os.path.join('a', 'b1', 'c', 'd2'))
        os.makedirs(os.path.join('a', 'b1', 'c', 'd3'))
        os.makedirs(os.path.join('a', 'b2'))
        os.makedirs(os.path.join('a', 'b3', 'c'))
        if not all_writable:
            os.chmod(os.path.join('a',  'b1', 'c'), 0o000)

    def test_fails_for_relative_path(self):
        with open('x', 'wb'):
            pass

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object('x')
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object(pathlib.Path('x'))
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object(dlb.fs.Path('x'))
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        self.assertTrue(os.path.isfile('x'))  # still exists

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object('')
        self.assertEqual("not an absolute path: ''", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object(pathlib.Path(''))
        self.assertEqual("not an absolute path: '.'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object(dlb.fs.Path('.'))
        self.assertEqual("not an absolute path: '.'", str(cm.exception))

    def test_removes_existing_regular_file(self):
        with open('f', 'wb'):
            pass

        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'f'))

        self.assertFalse(os.path.exists('f'))

    def test_removes_empty_directory(self):
        os.mkdir('d')

        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'd'))

        self.assertFalse(os.path.exists('d'))

    def test_removes_symbolic_link(self):
        with open('f', 'wb'):
            pass

        try:
            os.symlink('f', 's', target_is_directory=False)
            self.assertTrue(os.path.islink('s'))
        except (NotImplementedError, PermissionError):  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 's'))
        self.assertFalse(os.path.exists('s'))
        self.assertTrue(os.path.exists('f'))  # still exists

    def test_fails_for_nonexisting(self):
        with self.assertRaises(FileNotFoundError):
            dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'n'))

    def test_ignores_for_nonexisting_if_required(self):
        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'n'), ignore_non_existing=True)

    def test_removes_nonempty_directory_in_place(self):
        self.create_dir_a_in_cwd()
        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'a'))
        self.assertFalse(os.path.exists('a'))

    def test_removes_nonempty_directory_in_tmp(self):
        self.create_dir_a_in_cwd()
        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.fs.manip.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.abspath(abs_temp_dir_path))
        self.assertFalse(os.path.exists('a'))

    def test_removes_most_of_nonempty_directory_in_place_if_permission_denied_in_subdirectory(self):
        self.create_dir_a_in_cwd(all_writable=False)

        with self.assertRaises(PermissionError):
            try:
                dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'a'))
            finally:
                os.chmod(os.path.join('a', 'b1', 'c'), 0o777)

        self.assertTrue(os.path.exists('a'))  # still exists

    def test_removes_nonempty_directory_in_tmp_if_permission_denied_in_subdirectory(self):
        self.create_dir_a_in_cwd(all_writable=False)

        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.fs.manip.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.abspath(abs_temp_dir_path))
            os.chmod(os.path.join(abs_temp_dir_path, 't', 'b1', 'c'), 0o777)

        self.assertFalse(os.path.exists('a'))  # was successful
