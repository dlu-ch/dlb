import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

from dlb.cmd.context import Context
import unittest


class TestModule(unittest.TestCase):

    def test_import(self):
        import dlb.cmd.context
        self.assertEqual(['Context'], dlb.cmd.context.__all__)
        self.assertTrue('Tool' in dir(dlb.cmd))


class NestingTest(unittest.TestCase):

    def test_current_is_none_at_module_level(self):
        self.assertIsNone(Context.current())

    def test_can_by_nested(self):
        self.assertIsNone(Context.current())
        with Context() as c1:
            self.assertIs(Context.current(), c1)
            with Context() as c2:
                self.assertIs(Context.current(), c2)
            self.assertIs(Context.current(), c1)
        self.assertIsNone(Context.current())

    def test_nesting_error_is_detected(self):
        import dlb.cmd.context

        with self.assertRaises(dlb.cmd.context.NestingError):
            with Context():
                dlb.cmd.context._contexts.pop()
        dlb.cmd.context._contexts = []

        with self.assertRaises(dlb.cmd.context.NestingError):
            with Context():
                dlb.cmd.context._contexts.append('x')
        dlb.cmd.context._contexts = []
