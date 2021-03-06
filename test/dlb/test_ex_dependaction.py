# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex._depend
import dlb.ex._dependaction
import dlb.ex._tool
import unittest


class GetActionTest(unittest.TestCase):

    def test_has_dependency_and_name(self):
        a = dlb.ex._dependaction.get_action(dlb.ex.input.RegularFile(), 'a')
        self.assertIsInstance(a.dependency, dlb.ex.input.RegularFile)
        self.assertEqual('a', a.name)


class RegisterTest(unittest.TestCase):
    class DummyDependency(dlb.ex._depend.Dependency):
        Value = int

    class DummyAction(dlb.ex._dependaction.Action):
        pass

    def test_fails_for_registered_action(self):
        with self.assertRaises(ValueError):
            dlb.ex._dependaction.register_action(0, dlb.ex.input.RegularFile, dlb.ex._dependaction.DirectoryInputAction)

    def test_fails_for_registered_dependency_id(self):
        with self.assertRaises(ValueError):
            dlb.ex._dependaction.register_action(3, RegisterTest.DummyDependency, RegisterTest.DummyAction)

        with self.assertRaises(ValueError):
            dlb.ex._dependaction.register_action(3, dlb.ex.input.RegularFile,
                                                 dlb.ex._dependaction.RegularFileInputAction)

    def test_fails_for_abstract_dependency_class(self):
        with self.assertRaises(TypeError):
            dlb.ex._dependaction.register_action(3, dlb.ex._depend.InputDependency, RegisterTest.DummyAction)


class RegularFileInputPermanentLocalInstanceIdTest(unittest.TestCase):

    def test_is_equal_for_different_instances_with_same_arguments(self):
        d1 = dlb.ex.input.RegularFile()
        d2 = dlb.ex.input.RegularFile[:]()
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_require(self):
        d1 = dlb.ex.input.RegularFile(required=False)
        d2 = dlb.ex.input.RegularFile[:]()
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_cls(self):
        d1 = dlb.ex.input.RegularFile(cls=dlb.fs.NoSpacePath)
        d2 = dlb.ex.input.RegularFile[:]()
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)


class EnvVarFileInputPermanentLocalInstanceIdTest(unittest.TestCase):

    def test_is_equal_for_different_instances_with_same_arguments(self):
        d1 = dlb.ex.input.EnvVar(name='d', pattern='x.', example='xy')
        d2 = dlb.ex.input.EnvVar(name='d', pattern='x.', example='xy')
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_different_for_different_names(self):
        d1 = dlb.ex.input.EnvVar(name='d1', pattern='x.', example='xy')
        d2 = dlb.ex.input.EnvVar(name='d2', pattern='x.', example='xy')
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertNotEqual(plii1, plii2)

    def test_is_equal_for_different_validation_patterns(self):
        d1 = dlb.ex.input.EnvVar(name='d', pattern='x.', example='xy')
        d2 = dlb.ex.input.EnvVar(name='d', pattern='.y', example='xy')
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_example(self):
        d1 = dlb.ex.input.EnvVar(name='d', pattern='x.', example='xy')
        d2 = dlb.ex.input.EnvVar(name='d', pattern='x.', example='xz')
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)


class RegularFileOutputPermanentLocalInstanceIdTest(unittest.TestCase):

    def test_is_equal_for_different_instances_with_same_arguments(self):
        d1 = dlb.ex.output.RegularFile()
        d2 = dlb.ex.output.RegularFile[:]()
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)


class DifferentInputPermanentLocalInstanceIdTest(unittest.TestCase):
    def test_is_different_for_different_classes_with_same_arguments(self):
        d1 = dlb.ex.output.RegularFile()
        d2 = dlb.ex.output.NonRegularFile()
        plii1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertNotEqual(plii1, plii2)


class RegularFileInputPermanentLocalValueIdTest(unittest.TestCase):

    def test_is_different_for_different_value(self):
        d1 = dlb.ex.input.RegularFile()
        d2 = dlb.ex.input.RegularFile()
        plvi1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_value_id(
            d1.tuple_from_value(d1.validate('x')))
        plvi2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate('x/y')))
        self.assertNotEqual(plvi1, plvi2)

        d1 = dlb.ex.input.RegularFile[:]()
        d2 = dlb.ex.input.RegularFile[:]()
        plvi1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_value_id(
            d1.tuple_from_value(d1.validate(['x', 'y'])))
        plvi2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate(['a'])))
        self.assertNotEqual(plvi1, plvi2)

    def test_is_equal_for_different_cls(self):
        d1 = dlb.ex.input.RegularFile(cls=dlb.fs.NoSpacePath)
        d2 = dlb.ex.input.RegularFile()
        plvi1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_value_id(
            d1.tuple_from_value(d1.validate('x/y')))
        plvi2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate('x/y')))
        self.assertEqual(plvi1, plvi2)


class EnvVarInputPermanentLocalValueIdTest(unittest.TestCase):

    def test_is_different_for_different_value(self):
        d1 = dlb.ex.input.EnvVar(name='d', pattern='x.', example='xy')
        d2 = dlb.ex.input.EnvVar(name='d', pattern='x.', example='xy')
        plvi1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_value_id(d1.validate('xy'))
        plvi2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_value_id(d2.validate('x_'))
        self.assertNotEqual(plvi1, plvi2)

    def test_is_equal_for_different_validation_pattern(self):
        d1 = dlb.ex.input.EnvVar(name='d', pattern='x.', example='xy')
        d2 = dlb.ex.input.EnvVar(name='d', pattern='.y', example='xy')
        plvi1 = dlb.ex._dependaction.get_action(d1, 'd').get_permanent_local_value_id(d1.validate('xy'))
        plvi2 = dlb.ex._dependaction.get_action(d2, 'd').get_permanent_local_value_id(d2.validate('xy'))
        self.assertEqual(plvi1, plvi2)
