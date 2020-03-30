# SPDX-License-Identifier: LGPL-3.0-or-later
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
    class DummyDependency(dlb.ex.depend.Dependency):
        Value = int

    class DummyAction(dlb.ex.dependaction.Action):
        pass

    def test_fails_for_registered_action(self):
        with self.assertRaises(ValueError):
            dlb.ex.dependaction.register_action(0, dlb.ex.depend.RegularFileInput,
                                                dlb.ex.dependaction.DirectoryInputAction)

    def test_fails_for_registered_dependency_id(self):
        with self.assertRaises(ValueError):
            dlb.ex.dependaction.register_action(3, RegisterTest.DummyDependency, RegisterTest.DummyAction)

        with self.assertRaises(ValueError):
            dlb.ex.dependaction.register_action(3, dlb.ex.depend.RegularFileInput,
                                                dlb.ex.dependaction.RegularFileInputAction)

    def test_fails_for_abstract_dependency_class(self):
        with self.assertRaises(TypeError):
            dlb.ex.dependaction.register_action(3, dlb.ex.depend.Input, RegisterTest.DummyAction)


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

    def test_is_equal_for_different_cls(self):
        d1 = dlb.ex.Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath)
        d2 = dlb.ex.Tool.Input.RegularFile[:]()
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)


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


class EnvVarInputFilesystemOperationTest(unittest.TestCase):

    def test_fails_on_filesystem_operations(self):
        d = dlb.ex.Tool.Input.EnvVar(name='AB', restriction='x.', example='xy', explicit=False, required=False)
        a = dlb.ex.dependaction.get_action(d, 'd')

        with self.assertRaises(ValueError):
            # noinspection PyTypeChecker
            a.check_filesystem_object_memo(None)

        with self.assertRaises(ValueError):
            # noinspection PyTypeChecker
            a.replace_filesystem_object(None, None, None)
