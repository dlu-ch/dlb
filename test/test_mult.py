import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex.mult
import unittest
import random


class TestConstruction(unittest.TestCase):

    def test_succeeds_from_nonnegative_int(self):
        m = dlb.ex.mult.MultiplicityRange(3)
        self.assertEqual(slice(3, 3 + 1, 1), m.as_slice)

        m = dlb.ex.mult.MultiplicityRange(0)
        self.assertEqual(slice(0, 1, 1), m.as_slice)

    def test_succeeds_from_slice(self):
        m = dlb.ex.mult.MultiplicityRange(slice(1, 20, 3))
        self.assertEqual(slice(1, 20, 3), m.as_slice)

    def test_fails_from_none(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.mult.MultiplicityRange(None)
        self.assertEqual("'multiplicity' must be int or slice of int, not None", str(cm.exception))

    def test_fails_from_negative_int(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.mult.MultiplicityRange(-1)
        self.assertEqual("minimum multiplicity (start of slice) must be non-negative, not -1", str(cm.exception))

    def test_fails_from_slice_with_negative_elementstart_stop_or_step(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.mult.MultiplicityRange(slice(-1, 20, 3))
        self.assertEqual("minimum multiplicity (start of slice) must be non-negative, not -1", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex.mult.MultiplicityRange(slice(1, -20, 3))
        self.assertEqual("upper multiplicity bound (stop of slice) must be non-negative, not -20", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex.mult.MultiplicityRange(slice(1, 20, -3))
        self.assertEqual("slice step must be positive, not -3", str(cm.exception))

    def test_fails_from_noninteger_slice(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.mult.MultiplicityRange(slice('1', 20, 3))
        self.assertEqual("slice step must be positive, not -3", str(cm.exception))

    def test_fails_from_noninteger_slice(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.mult.MultiplicityRange(slice('1', 20, 3))
        self.assertEqual("'multiplicity' must be int or slice of int, not slice('1', 20, 3)", str(cm.exception))

    def test_normalizes_empty_slice(self):
        m = dlb.ex.mult.MultiplicityRange(slice(3, 3, 20))
        self.assertEqual(m.as_slice, slice(0, 0, 1))

    def test_normalizes_slice_with_only_one_member(self):
        m = dlb.ex.mult.MultiplicityRange(slice(3, 23, 20))
        self.assertEqual(m.as_slice, slice(3, 4, 1))


class TestCompare(unittest.TestCase):

    def test_normalized_equal_are_equal(self):
        m1 = dlb.ex.mult.MultiplicityRange(slice(2, 2))
        m2 = dlb.ex.mult.MultiplicityRange(slice(5, 2, 7))
        self.assertTrue(m1 == m2)
        self.assertFalse(m1 != m2)

        m1 = dlb.ex.mult.MultiplicityRange(5)
        m2 = dlb.ex.mult.MultiplicityRange(slice(5, 6, 7))
        self.assertTrue(m1 == m2)
        self.assertFalse(m1 != m2)

    def test_different_are_not_equal(self):
        m1 = dlb.ex.mult.MultiplicityRange(3)
        m2 = dlb.ex.mult.MultiplicityRange(4)
        self.assertTrue(m1 != m2)
        self.assertFalse(m1 == m2)


class TestStr(unittest.TestCase):

    def test_empty_is_correct(self):
        m = dlb.ex.mult.MultiplicityRange(slice(2, 2))
        self.assertEqual('[:0]', str(m))

    def test_minimum_is_correct(self):
        m = dlb.ex.mult.MultiplicityRange(slice(3, None))
        self.assertEqual('[3:]', str(m))

    def test_upper_bound_is_correct(self):
        m = dlb.ex.mult.MultiplicityRange(slice(None, 4))
        self.assertEqual('[:4]', str(m))

    def test_unrestricted_is_correct(self):
        m = dlb.ex.mult.MultiplicityRange(slice(None))
        self.assertEqual('[:]', str(m))


class TestRepr(unittest.TestCase):

    def test_upper_bound_is_correct(self):
        m = dlb.ex.mult.MultiplicityRange(slice(None, 4))
        self.assertEqual('MultiplicityRange(slice(0, 4, 1))', repr(m))


class TestMatchesCount(unittest.TestCase):

    def test_integer_matches_exact_count(self):
        m = dlb.ex.mult.MultiplicityRange(2)
        self.assertTrue(2 in m)
        self.assertFalse(1 in m)
        self.assertFalse(3 in m)

    def test_empty_slice_matches_nothing(self):
        m = dlb.ex.mult.MultiplicityRange(slice(0, 0, 4))
        self.assertFalse(0 in m)
        self.assertFalse(2 in m)

    def test_slice_matches_like_builtin(self):
        top = 50

        for i in range(1000):
            start = random.randrange(-1, top)
            stop = random.randrange(-1, top)
            step = random.randrange(0, top // 10)
            i = tuple(i for i in range(top + 1))
            try:
                s = slice(start, stop, step)
                m = dlb.ex.mult.MultiplicityRange(s)
                for j in range(100):
                    n = random.randrange(start, stop + 1)
                    self.assertEqual(n in i[s], n in m, f'{n} in {s}?')
            except ValueError:
                pass


class TestMultiplicityHolder(unittest.TestCase):

    class M(dlb.ex.mult.MultiplicityHolder):
        def __init__(self, a, b=1):
            super().__init__()

    def test_has_no_multiplicity_when_constructed_directly(self):
        m = TestMultiplicityHolder.M(1, b=2)
        self.assertIsInstance(m, TestMultiplicityHolder.M)
        self.assertIsNone(m.multiplicity)

    def test_has_multiplicity_when_constructed_by_slice(self):
        m = TestMultiplicityHolder.M[:3](1, b=2)
        self.assertIsInstance(m, TestMultiplicityHolder.M)
        self.assertEqual(dlb.ex.mult.MultiplicityRange(slice(0, 3)), m.multiplicity)

    def test_fails_for_nested_multiplicity(self):
        with self.assertRaises(TypeError) as cm:
            TestMultiplicityHolder.M[:3][2](1, b=2)
        self.assertEqual("'M' with multiplicity is not subscriptable", str(cm.exception))

    def test_multiplicity_cannot_be_assigned(self):
        with self.assertRaises(AttributeError):
            TestMultiplicityHolder.M(1, b=2).multiplicity = None

    def test_name_contains_multiplicity(self):
        M = TestMultiplicityHolder.M[:3]
        self.assertEqual(TestMultiplicityHolder.M.__name__ + '[:3]', M.__name__)
        self.assertEqual(TestMultiplicityHolder.M.__qualname__ + '[:3]', M.__qualname__)

    def test_repr_is_meaningful(self):
        r = repr(TestMultiplicityHolder.M[:3])
        regex = (
            r"\A<dlb\.ex\.mult\._MultiplicityHolderProxy object at 0x[0-9a-fA-F]+ for "
            r"<class 'test_mult\.TestMultiplicityHolder\.M'> with multiplicity \[:3\]>\Z"
        )
        self.assertRegex(r, regex)
