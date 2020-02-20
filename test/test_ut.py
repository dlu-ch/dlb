# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ut
import collections
import unittest


class MakeFundamentalTest(unittest.TestCase):

    def test_returns_none_for_none(self):
        self.assertIsNone(dlb.ut.make_fundamental(None))

    def test_returns_frozenset_for_set(self):
        s = {1, 2, 3}
        r = dlb.ut.make_fundamental(s)
        self.assertIsInstance(r, frozenset)
        self.assertEqual(r, s)

        r = dlb.ut.make_fundamental(s, True)
        self.assertEqual((1, 2, 3), r)

    def test_returns_dict_for_ordereddict(self):
        d = collections.OrderedDict([(1, 2), (3, 4)])

        r = dlb.ut.make_fundamental(d)
        self.assertIsInstance(r, dict)
        self.assertEqual(r, d)

        r = dlb.ut.make_fundamental(d, True)
        self.assertEqual(((1, 2), (3, 4)), r)

    def test_fails_for_recursive_list(self):
        l = [1]
        l.append(l)
        with self.assertRaises(TypeError):
            dlb.ut.make_fundamental(dlb.ut.make_fundamental(l))

    def test_example_is_correct(self):
        s = [
            (1, 2.5, False),
            [{6, 9, 13}, ['hello'], complex(7, 8)],
            {b'abc': None}
        ]

        r = dlb.ut.make_fundamental(s)
        self.assertEqual((
            (1, 2.5, False),
            (frozenset([6, 9, 13]), ('hello',), complex(7, 8)),
            {b'abc': None}
        ), r)

        r = dlb.ut.make_fundamental(s, True)
        self.assertEqual((
            (1, 2.5, False),
            ((6, 9, 13), ('hello',), complex(7, 8)),
            ((b'abc', None),)
        ), r)

    def test_fails_for_dummy_class(self):
        class A:
            pass

        with self.assertRaises(TypeError):
            dlb.ut.make_fundamental(A())


class ExceptionToLine(unittest.TestCase):

    def test_uses_classname_if_no_message(self):
        msg = dlb.ut.exception_to_line(Exception())
        self.assertEqual('builtins.Exception', msg)

        msg = dlb.ut.exception_to_line(Exception('\t    '))
        self.assertEqual('builtins.Exception', msg)

        msg = dlb.ut.exception_to_line(Exception(' \rA'))
        self.assertEqual('builtins.Exception', msg)

    def test_uses_first_line_if_message(self):
        msg = dlb.ut.exception_to_line(Exception('  hehe  \r\n'))
        self.assertEqual('hehe', msg)

    def test_uses_classname_and_first_line_if_message_and_forced(self):
        msg = dlb.ut.exception_to_line(Exception('  hehe  \r\n'), True)
        self.assertEqual('builtins.Exception: hehe', msg)
