# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ut
import dataclasses
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

    def test_returns_bytes_for_str(self):
        r = dlb.ut.make_fundamental('xyz', True)
        self.assertEqual(b'sxyz', r)

    def test_returns_bytes_for_bytes(self):
        r = dlb.ut.make_fundamental(b'xyz', True)
        self.assertEqual(b'bxyz', r)

    def test_returns_tuple_for_dataclass(self):
        @dataclasses.dataclass
        class D:
            a: str
            b: int

        d = D('ui', 0)
        r = dlb.ut.make_fundamental(d, True)
        self.assertEqual(dataclasses.astuple(d), r)

    def test_fails_for_recursive_list(self):
        li = [1]
        li.append(li)
        with self.assertRaises(TypeError):
            dlb.ut.make_fundamental(dlb.ut.make_fundamental(li))

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
            ((6, 9, 13), (b'shello',), complex(7, 8)),
            ((b'babc', None),)
        ), r)

    def test_fails_for_dummy_class(self):
        class A:
            pass

        with self.assertRaises(TypeError):
            dlb.ut.make_fundamental(A())


class ExceptionToLineTest(unittest.TestCase):

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


class FormatTimeNsTest(unittest.TestCase):

    def test_zero_is_correct(self):
        self.assertEqual('0.000000000', dlb.ut.format_time_ns(0))
        self.assertEqual('0.000000000000', dlb.ut.format_time_ns(0, 12))
        self.assertEqual('0.0', dlb.ut.format_time_ns(0, -12))

    def test_small_positive_is_correct(self):
        self.assertEqual('0.000000123', dlb.ut.format_time_ns(123))
        self.assertEqual('0.000000123000', dlb.ut.format_time_ns(123, 12))
        self.assertEqual('0.0000001', dlb.ut.format_time_ns(123, 7))
        self.assertEqual('0.0', dlb.ut.format_time_ns(123, -12))

    def test_small_negative_is_correct(self):
        self.assertEqual('-0.000000123', dlb.ut.format_time_ns(-123))
        self.assertEqual('-0.000000123000', dlb.ut.format_time_ns(-123, 12))
        self.assertEqual('-0.0000001', dlb.ut.format_time_ns(-123, 7))
        self.assertEqual('-0.0', dlb.ut.format_time_ns(-123, -12))

    def test_large_positive_is_correct(self):
        self.assertEqual('1267650600228229401496.703205376', dlb.ut.format_time_ns(2**100))

    def test_large_negative_is_correct(self):
        self.assertEqual('-1267650600228229401496.703205376', dlb.ut.format_time_ns(-2**100))
