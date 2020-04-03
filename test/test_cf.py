# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import inspect
import dlb.cf
import unittest


class ImportTest(unittest.TestCase):
    def test_contains_only_declared_modules(self):
        modules = [n for n in dir(dlb.cf) if inspect.ismodule(getattr(dlb.cf, n))]
        self.assertEqual(['level'], modules)

    def test_level_contains_no_module(self):
        modules = [n for n in dir(dlb.cf.level) if inspect.ismodule(getattr(dlb.cf.level, n))]
        self.assertEqual([], modules)
