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
        d1 = dlb.ex.Tool.Input.EnvVar(restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar[:](restriction='x.', example='xy')
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_restriction(self):
        d1 = dlb.ex.Tool.Input.EnvVar(restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar[:](restriction='.y', example='xy')
        plii1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_instance_id()
        plii2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_instance_id()
        self.assertEqual(plii1, plii2)

    def test_is_equal_for_different_example(self):
        d1 = dlb.ex.Tool.Input.EnvVar(restriction='x.', example='xy')
        d2 = dlb.ex.Tool.Input.EnvVar[:](restriction='x.', example='xz')
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
            d1.tuple_from_value(d1.validate('x', None)))
        plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate('x/y', None)))
        self.assertNotEqual(plvi1, plvi2)

        d1 = dlb.ex.Tool.Input.RegularFile[:]()
        d2 = dlb.ex.Tool.Input.RegularFile[:]()
        plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(
            d1.tuple_from_value(d1.validate(['x', 'y'], None)))
        plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate(['a'], None)))
        self.assertNotEqual(plvi1, plvi2)

    def test_is_equal_for_different_cls(self):
        d1 = dlb.ex.Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath)
        d2 = dlb.ex.Tool.Input.RegularFile()
        plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(
            d1.tuple_from_value(d1.validate('x/y', None)))
        plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(
            d2.tuple_from_value(d2.validate('x/y', None)))
        self.assertEqual(plvi1, plvi2)


class EnvVarInputPermanentLocalValueIdTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_is_different_for_different_value(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context() as c:
            c.env.import_from_outer('UV', r'.*', '')
            c.env.import_from_outer('AB', r'.*', '')
            c.env['UV'] = 'xy'
            c.env['AB'] = 'xz'

            d1 = dlb.ex.Tool.Input.EnvVar(restriction='x.', example='xy')
            d2 = dlb.ex.Tool.Input.EnvVar(restriction='x.', example='xy')
            plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(d1.validate('UV', c))
            plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(d2.validate('AB', c))
            self.assertNotEqual(plvi1, plvi2)

            d1 = dlb.ex.Tool.Input.EnvVar[:](restriction='x.', example='xy')
            d2 = dlb.ex.Tool.Input.EnvVar[:](restriction='x.', example='xy')
            plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(d1.validate(['AB', 'UV'], c))
            plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(d2.validate(['UV', 'AB'], c))
            self.assertNotEqual(plvi1, plvi2)

    def test_is_equal_for_different_restriction(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context() as c:
            c.env.import_from_outer('UV', r'.*', '')
            c.env.import_from_outer('AB', r'.*', '')
            c.env['UV'] = 'xy'
            c.env['AB'] = 'xy'

            d1 = dlb.ex.Tool.Input.EnvVar(restriction='x.', example='xy')
            d2 = dlb.ex.Tool.Input.EnvVar(restriction='.y', example='xy')
            plvi1 = dlb.ex.dependaction.get_action(d1, 'd').get_permanent_local_value_id(d1.validate('UV', c))
            plvi2 = dlb.ex.dependaction.get_action(d2, 'd').get_permanent_local_value_id(d2.validate('UV', c))
            self.assertEqual(plvi1, plvi2)
