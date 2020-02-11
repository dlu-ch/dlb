import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex.tool2.dependency
import dlb.ex.mult
import unittest


class TestDependency(unittest.TestCase):

    def test_is_multiplicity_holder(self):
        d = dlb.ex.tool2.dependency.Dependency()
        self.assertIsInstance(d, dlb.ex.mult.MultiplicityHolder)

    def test_validate_fail_with_meaningful_message(self):
        msg = (
            "<class 'dlb.ex.tool2.dependency.Dependency'> is abstract\n"
            "  | use one of its documented subclasses instead"
        )

        d = dlb.ex.tool2.dependency.Dependency()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate('', None)
        self.assertEqual(msg, str(cm.exception))

        d = dlb.ex.tool2.dependency.Dependency[:]()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate([1], None)
        self.assertEqual(msg, str(cm.exception))

    def test_validate_with_str_of_bytes_fails_with_meaningful_message(self):
        msg = 'since dependency has a multiplicity, value must be iterable (other than string or bytes)'
        d = dlb.ex.tool2.dependency.Dependency[:]()

        with self.assertRaises(TypeError) as cm:
            d.validate('', None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            d.validate(b'', None)
        self.assertEqual(msg, str(cm.exception))

    def test_validate_with_multiplicity_mismatch_fails_with_meaningful_message(self):
        d = dlb.ex.tool2.dependency.Dependency[1:]()
        with self.assertRaises(ValueError) as cm:
            d.validate([], None)
        msg = 'value has 0 members, which is not accepted according to the specified multiplicity [1:]'
        self.assertEqual(msg, str(cm.exception))
