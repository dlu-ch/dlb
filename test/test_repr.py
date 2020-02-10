import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

from dlb.ex.repr import make_fundamental
import collections
import unittest


class MakeFundamentalTest(unittest.TestCase):

    def test_returns_none_for_none(self):
        self.assertIsNone(make_fundamental(None))

    def test_returns_frozenset_for_set(self):
        s = set([1, 2, 3])
        r = make_fundamental(s)
        self.assertIsInstance(r, frozenset)
        self.assertEqual(r, s)

        r = make_fundamental(s, True)
        self.assertEqual((1, 2, 3), r)

    def test_returns_dict_for_ordereddict(self):
        d = collections.OrderedDict([(1, 2), (3, 4)])

        r = make_fundamental(d)
        self.assertIsInstance(r, dict)
        self.assertEqual(r, d)

        r = make_fundamental(d, True)
        self.assertEqual(((1, 2), (3, 4)), r)

    def test_fails_for_recursive_list(self):
        l = [1]
        l.append(l)
        with self.assertRaises(TypeError):
            make_fundamental(make_fundamental(l))

    def test_example_is_correct(self):
        s = [
            (1, 2.5, False),
            [{6, 9, 13}, ['hello'], complex(7, 8)],
            {b'abc': None}
        ]

        r = make_fundamental(s)
        self.assertEqual((
            (1, 2.5, False),
            (frozenset([6, 9, 13]), ('hello',), complex(7, 8)),
            {b'abc': None}
        ), r)

        r = make_fundamental(s, True)
        self.assertEqual((
            (1, 2.5, False),
            ((6, 9, 13), ('hello',), complex(7, 8)),
            ((b'abc', None),)
        ), r)

    def test_fails_for_dummy_class(self):
        class A:
            pass

        with self.assertRaises(TypeError):
            make_fundamental(A())
