# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2021 Daniel Lutz <dlu-ch@users.noreply.github.com>
import os.path

import testenv  # also sets up module search paths
import dlb.fs
import dlb_contrib.python
import sys
import unittest


class PrependToModuleSearchPathTest(unittest.TestCase):

    def test_example_is_correct(self):
        path0 = list(sys.path)
        try:
            sys.path.append(os.path.realpath(os.path.join('build', 'python')))

            build_directory = dlb.fs.Path('build/')
            dlb_contrib.python.prepend_to_module_search_path(
                build_directory / 'python/',
                build_directory / 'out/gsrc/python/'
            )

            self.assertEqual(len(path0) + 2, len(sys.path))
            self.assertEqual(path0, sys.path[2:])

            self.assertTrue(os.path.isabs(sys.path[0]))
            self.assertEqual(os.path.realpath(os.path.join('build', 'python')), sys.path[0])

            self.assertTrue(os.path.isabs(sys.path[1]))
            self.assertEqual(os.path.realpath(os.path.join('build', 'out', 'gsrc', 'python')), sys.path[1])

            path1 = list(sys.path)
            dlb_contrib.python.prepend_to_module_search_path('build/python/')
            self.assertEqual(path1, sys.path)  # unchanged
        finally:
            sys.path = path0

    def test_fails_for_nondirectory_path(self):
        path0 = list(sys.path)
        try:
            msg = "cannot prepend non-directory: 'build/python'"

            with self.assertRaises(ValueError) as cm:
                dlb_contrib.python.prepend_to_module_search_path(dlb.fs.Path('build/python'))
            self.assertEqual(msg, str(cm.exception))

            with self.assertRaises(ValueError) as cm:
                dlb_contrib.python.prepend_to_module_search_path('build/python')
            self.assertEqual(msg, str(cm.exception))
        finally:
            sys.path = path0

    def test_empty_does_not_change_path(self):
        path0 = list(sys.path)
        try:
            dlb_contrib.python.prepend_to_module_search_path()
            self.assertEqual(path0, sys.path)  # unchanged
        finally:
            sys.path = path0
