import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.cmd
import dlb.cmd.context
import unittest


class TestModule(unittest.TestCase):

    def test_import(self):
        import dlb.cmd.context
        self.assertEqual(['Context'], dlb.cmd.context.__all__)
        self.assertTrue('Tool' in dir(dlb.cmd))


class NestingTest(unittest.TestCase):

    def test_none_active_at_module_level(self):
        with self.assertRaises(dlb.cmd.context.NoneActive):
            dlb.cmd.Context.active

    def test_no_root_at_module_level(self):
        with self.assertRaises(dlb.cmd.context.NoneActive):
            dlb.cmd.Context.root

    def test_can_by_nested(self):
        with dlb.cmd.Context() as c1:
            self.assertIs(dlb.cmd.Context.active, c1)
            self.assertIs(dlb.cmd.Context.root, c1)

            with dlb.cmd.Context() as c2:
                self.assertIs(dlb.cmd.Context.active, c2)
                self.assertIs(dlb.cmd.Context.root, c1)

            self.assertIs(dlb.cmd.Context.active, c1)
            self.assertIs(dlb.cmd.Context.root, c1)

        with self.assertRaises(dlb.cmd.context.NoneActive):
            dlb.cmd.Context.active
        with self.assertRaises(dlb.cmd.context.NoneActive):
            dlb.cmd.Context.root

    def test_nesting_error_is_detected(self):
        import dlb.cmd.context

        with self.assertRaises(dlb.cmd.context.NestingError):
            with dlb.cmd.Context():
                dlb.cmd.context._contexts.pop()
        dlb.cmd.context._contexts = []

        with self.assertRaises(dlb.cmd.context.NestingError):
            with dlb.cmd.Context():
                dlb.cmd.context._contexts.append('x')
        dlb.cmd.context._contexts = []


class AttributeProtection(unittest.TestCase):

    def test_active_attribute_is_readonly(self):
        with self.assertRaises(AttributeError):
            dlb.cmd.Context.active = None

    def test_root_attribute_is_readonly(self):
        with self.assertRaises(AttributeError):
            dlb.cmd.Context.root = None


class DirectoryNameTest(unittest.TestCase):

    def test_working_dir_cache_name_is_portable(self):
        import dlb.fs
        dlb.fs.PortablePath(dlb.cmd.Context.MANAGINGTREE_DIR_NAME)
