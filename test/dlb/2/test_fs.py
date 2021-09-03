# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import sys
import pathlib
import unittest


class BrokenPathlibPathTest(unittest.TestCase):

    def test_fails_at_construction_from_nonabsolute_without_anchor(self):
        self.assertNotIn('dlb', sys.modules)

        class CustomPosixPath(pathlib.PurePosixPath):
            def is_absolute(self):
                return False

        pathlib.Path = CustomPosixPath
        pathlib.PosixPath = CustomPosixPath

        import dlb.fs

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path.Native('/x/y')
        self.assertEqual("'path' is neither relative nor absolute", str(cm.exception))
