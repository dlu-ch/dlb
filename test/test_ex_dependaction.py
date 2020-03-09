# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex.depend
import dlb.ex.dependaction
import dlb.ex.tool
import unittest
import tools_for_test


class GetActionTest(unittest.TestCase):

    def test_has_dependency_and_name(self):
        a = dlb.ex.dependaction.get_action(dlb.ex.depend.RegularFileInput(), 'a')
        self.assertIsInstance(a.dependency, dlb.ex.depend.RegularFileInput)
        self.assertEqual('a', a.name)


class RegisterTest(unittest.TestCase):

    def test_fails_for_registered_action(self):
        with self.assertRaises(ValueError):
            dlb.ex.dependaction.register_action(-1, dlb.ex.depend.RegularFileInput,
                                                dlb.ex.dependaction.RegularFileInputAction)

    def test_fails_for_registered_dependency_id(self):

        class DummyAction(dlb.ex.dependaction.Action):
            pass

        with self.assertRaises(ValueError):
            dlb.ex.dependaction.register_action(3, dlb.ex.depend.RegularFileInput, DummyAction)


class RegularFileInputPermanentLocalInstanceIdTest(unittest.TestCase):

    def test_is_equal_for_different_instances_with_same_arguments(self):
        d1 = dlb.ex.Tool.Input.RegularFile()
        d2 = dlb.ex.Tool.Input.RegularFile[:]()
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_require(self):
        d1 = dlb.ex.Tool.Input.RegularFile(required=False)
        d2 = dlb.ex.Tool.Input.RegularFile[:]()
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_unique(self):
        d1 = dlb.ex.Tool.Input.RegularFile(unique=False)
        d2 = dlb.ex.Tool.Input.RegularFile[:]()
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_cls(self):
        d1 = dlb.ex.Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath)
        d2 = dlb.ex.Tool.Input.RegularFile[:]()
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_different_for_different_unique(self):
        d1 = dlb.ex.Tool.Input.RegularFile(explicit=False)
        d2 = dlb.ex.Tool.Input.RegularFile[:]()
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertNotEqual(plii1, plii2)


class EnvVarFileInputPermanentLocalInstanceIdTest(unittest.TestCase):

    def test_is_equal_for_different_instances_with_same_arguments(self):
        d1 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='x.', example='xy')
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_different_for_different_names(self):
        d1 = dlb.ex.Tool.Input.EnvVar(name='d1', restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar(name='d2', restriction='x.', example='xy')
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertNotEqual(plii1, plii2)

    def test_is_equal_for_different_restriction(self):
        d1 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='.y', example='xy')
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_example(self):
        d1 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='x.', example='xz')
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)


class RegularFileOutputPermanentLocalInstanceIdTest(unittest.TestCase):

    def test_is_equal_for_different_instances_with_same_arguments(self):
        d1 = dlb.ex.Tool.Output.RegularFile()
        d2 = dlb.ex.Tool.Output.RegularFile[:]()
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)


class DifferentInputPermanentLocalInstanceIdTest(unittest.TestCase):
    def test_is_different_for_different_classes_with_same_arguments(self):
        d1 = dlb.ex.Tool.Output.RegularFile()
        d2 = dlb.ex.Tool.Output.NonRegularFile()
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertNotEqual(plii1, plii2)


class RegularFileInputPermanentLocalValueIdTest(unittest.TestCase):

    def test_is_different_for_different_value(self):
        d1 = dlb.ex.Tool.Input.RegularFile()
        d2 = dlb.ex.Tool.Input.RegularFile()
        plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(
            d1.tuple_from_value(d1.validate('x')))
        plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate('x/y')))
        self.assertNotEqual(plvi1, plvi2)

        d1 = dlb.ex.Tool.Input.RegularFile[:]()
        d2 = dlb.ex.Tool.Input.RegularFile[:]()
        plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(
            d1.tuple_from_value(d1.validate(['x', 'y'])))
        plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate(['a'])))
        self.assertNotEqual(plvi1, plvi2)

    def test_is_equal_for_different_cls(self):
        d1 = dlb.ex.Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath)
        d2 = dlb.ex.Tool.Input.RegularFile()
        plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(
            d1.tuple_from_value(d1.validate('x/y')))
        plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate('x/y')))
        self.assertEqual(plvi1, plvi2)


class EnvVarInputPermanentLocalValueIdTest(unittest.TestCase):

    def test_is_different_for_different_value(self):
        d1 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='x.', example='xy')
        plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(d1.validate('xy'))
        plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(d2.validate('x_'))
        self.assertNotEqual(plvi1, plvi2)

    def test_is_equal_for_different_restriction(self):
        d1 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar(name='d', restriction='.y', example='xy')
        plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(d1.validate('xy'))
        plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(d2.validate('xy'))
        self.assertEqual(plvi1, plvi2)


class EnvVarInitialResultTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_returns_none_if_nonrequired_not_defined(self):
        d = dlb.ex.Tool.Input.EnvVar(name='AB', restriction='x.', example='xy', explicit=False, required=False)
        a = dlb.ex.dependaction.get_action(d, 'd')

        try:
            del os.environ['AB']
        except KeyError:
            pass

        with dlb.ex.Context() as c:
            self.assertIsNone(a.get_initial_result_for_nonexplicit(c))
            c.env.import_from_outer('AB', r'.*', '')

            self.assertIsNone(a.get_initial_result_for_nonexplicit(c))
            c.env['AB'] = 'xy'
            self.assertEqual('xy', a.get_initial_result_for_nonexplicit(c))
            c.env['AB'] = 'x_'
            self.assertEqual('x_', a.get_initial_result_for_nonexplicit(c))

    def test_fails_if_required_not_defined(self):
        d = dlb.ex.Tool.Input.EnvVar(name='AB', restriction='x.', example='xy', explicit=False)
        a = dlb.ex.dependaction.get_action(d, 'd')

        try:
            del os.environ['AB']
        except KeyError:
            pass

        msg = (
            "not a defined environment variable in the context: 'AB'\n"
            "  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...]' = ..."
        )

        with dlb.ex.Context() as c:
            with self.assertRaises(ValueError) as cm:
                a.get_initial_result_for_nonexplicit(c)
            self.assertEqual(msg, str(cm.exception))

            c.env.import_from_outer('AB', r'.*', '')
            with self.assertRaises(ValueError) as cm:
                a.get_initial_result_for_nonexplicit(c)
            self.assertEqual(msg, str(cm.exception))


class EnvVarInputFilesystemOperationTest(unittest.TestCase):

    def test_fails_on_filesystem_operations(self):
        d = dlb.ex.Tool.Input.EnvVar(name='AB', restriction='x.', example='xy', explicit=False, required=False)
        a = dlb.ex.dependaction.get_action(d, 'd')

        with self.assertRaises(ValueError):
            a.check_filesystem_object_memo(None)

        with self.assertRaises(ValueError):
            a.replace_filesystem_object(None, None, None)
