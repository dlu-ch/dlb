# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb_contrib_c
import unittest


class RegexTest(unittest.TestCase):

    def test_identifier(self):
        self.assertTrue(dlb_contrib_c.IDENTIFIER.match('_a1Z'))
        self.assertTrue(dlb_contrib_c.IDENTIFIER.match('a' * 63))

        self.assertFalse(dlb_contrib_c.IDENTIFIER.match(''))
        self.assertFalse(dlb_contrib_c.IDENTIFIER.match('1a'))
        self.assertFalse(dlb_contrib_c.IDENTIFIER.match('a' * 64))

    def test_macro(self):
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z()'))
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(x)'))
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(...)'))
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(x, y, ...)'))
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(  x  , y  , ...  )'))

        self.assertEqual('_a1Z', dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(x, y, ...)').group('name'))
        self.assertEqual('x, y, ...', dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(x, y, ...)').group('arguments'))

        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z'))
        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z ()'))
        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z('))
        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z( ..., x )'))
        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z( x, ..., y )'))
