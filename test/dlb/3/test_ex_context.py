# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import sys
import os.path
import tempfile
import zipfile
import inspect
import unittest

import dlb.ex


class ThisIsAUnitTest(unittest.TestCase):
    pass


class WorkingTreeCaseSensitivityTest(testenv.TemporaryDirectoryTestCase):

    def test_fails_if_not_running(self):
        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex.NotRunningError):
            c.is_working_tree_case_sensitive

    def test_is_working_tree_case_sensitive(self):
        orig_lstat = os.lstat

        probeu_file_path = os.path.join(os.getcwd(), '.dlbroot', 'O')
        fake_probeu_file_path = probeu_file_path

        def lstat_except_probe(path, *, dir_fd=None):
            if path == probeu_file_path:
                path = fake_probeu_file_path
            return orig_lstat(path, dir_fd=dir_fd)

        os.lstat = lstat_except_probe
        os.mkdir('.dlbroot')

        try:

            fake_probeu_file_path = os.path.join(os.getcwd(), '.dlbroot', 'o')  # fake case-insensitive filesystem
            with dlb.ex.Context():
                self.assertFalse(dlb.ex.Context.active.is_working_tree_case_sensitive)

            fake_probeu_file_path = os.path.join(os.getcwd(), 'o')  # fake case-sensitive filesystem
            with dlb.ex.Context():
                self.assertTrue(dlb.ex.Context.active.is_working_tree_case_sensitive)

            open('o', 'xb').close()
            fake_probeu_file_path = os.path.join(os.getcwd(), 'o')  # fake case-sensitive filesystem
            with dlb.ex.Context():
                self.assertTrue(dlb.ex.Context.active.is_working_tree_case_sensitive)

        finally:
            os.lstat = orig_lstat
