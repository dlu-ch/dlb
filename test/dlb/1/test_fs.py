# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import sys
import pathlib
import unittest


class ImportWithUnsupportedPathlibPath(unittest.TestCase):

    def test_fails(self):  # must be only test executed in Python process
        self.assertNotIn('dlb', sys.modules)

        with self.assertRaises(TypeError) as cm:
            pathlib.Path = str
            import dlb.fs

        self.assertEqual("unsupported 'pathlib.Path' class", str(cm.exception))
