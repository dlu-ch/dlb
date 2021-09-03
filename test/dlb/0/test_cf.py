# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.cf
import inspect
import unittest


class ImportTest(unittest.TestCase):
    def test_contains_only_declared_modules(self):
        modules = [n for n in dir(dlb.cf) if inspect.ismodule(getattr(dlb.cf, n))]
        self.assertEqual(['level'], modules)

    def test_level_contains_no_module(self):
        modules = [n for n in dir(dlb.cf.level) if inspect.ismodule(getattr(dlb.cf.level, n))]
        self.assertEqual([], modules)
