import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex
import dlb.ex.context
import unittest


class TestModule(unittest.TestCase):

    def test_import(self):
        import dlb.ex.context
        self.assertEqual(['Context'], dlb.ex.context.__all__)
        self.assertTrue('Tool' in dir(dlb.ex))


class NestingTest(unittest.TestCase):

    def test_none_active_at_module_level(self):
        with self.assertRaises(dlb.ex.context.NoneActive):
            dlb.ex.Context.active

    def test_no_root_at_module_level(self):
        with self.assertRaises(dlb.ex.context.NoneActive):
            dlb.ex.Context.root

    def test_can_by_nested(self):
        with dlb.ex.Context() as c1:
            self.assertIs(dlb.ex.Context.active, c1)
            self.assertIs(dlb.ex.Context.root, c1)

            with dlb.ex.Context() as c2:
                self.assertIs(dlb.ex.Context.active, c2)
                self.assertIs(dlb.ex.Context.root, c1)

            self.assertIs(dlb.ex.Context.active, c1)
            self.assertIs(dlb.ex.Context.root, c1)

        with self.assertRaises(dlb.ex.context.NoneActive):
            dlb.ex.Context.active
        with self.assertRaises(dlb.ex.context.NoneActive):
            dlb.ex.Context.root

    def test_nesting_error_is_detected(self):
        import dlb.ex.context

        with self.assertRaises(dlb.ex.context.NestingError):
            with dlb.ex.Context():
                dlb.ex.context._contexts.pop()
        dlb.ex.context._contexts = []

        with self.assertRaises(dlb.ex.context.NestingError):
            with dlb.ex.Context():
                dlb.ex.context._contexts.append('x')
        dlb.ex.context._contexts = []


class AttributeProtection(unittest.TestCase):

    def test_active_attribute_is_readonly(self):
        with self.assertRaises(AttributeError):
            dlb.ex.Context.active = None

    def test_root_attribute_is_readonly(self):
        with self.assertRaises(AttributeError):
            dlb.ex.Context.root = None


class DirectoryNameTest(unittest.TestCase):

    def test_working_dir_cache_name_is_portable(self):
        import dlb.fs
        dlb.fs.PortablePath(dlb.ex.Context.MANAGINGTREE_DIR_NAME)
