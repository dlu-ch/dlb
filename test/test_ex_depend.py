# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex.mult
import dlb.ex.depend
import re
from typing import Tuple, Type
import unittest


filesystem_dependency_classes: Tuple[Type[dlb.ex.depend.Dependency], ...] = (
    dlb.ex.depend.RegularFileInput,
    dlb.ex.depend.NonRegularFileInput,
    dlb.ex.depend.DirectoryInput,
    dlb.ex.depend.RegularFileOutput,
    dlb.ex.depend.NonRegularFileOutput,
    dlb.ex.depend.DirectoryOutput
)


class BaseDependencyTest(unittest.TestCase):

    def test_is_multiplicity_holder(self):
        d = dlb.ex.depend.Dependency()
        self.assertIsInstance(d, dlb.ex.mult.MultiplicityHolder)

    def test_validate_fail_with_meaningful_message(self):
        msg = (
            "<class 'dlb.ex.Tool.Dependency'> is an abstract dependency class\n"
            "  | use one of its documented subclasses instead"
        )

        d = dlb.ex.depend.Dependency()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate('')
        self.assertEqual(msg, str(cm.exception))

        d = dlb.ex.depend.Dependency[:]()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate([1])
        self.assertEqual(msg, str(cm.exception))


class CommonOfConcreteValidationTest(unittest.TestCase):

    # stands for any non-abstract subclass of Dependency:
    D = dlb.ex.depend.RegularFileInput

    # noinspection PyPep8Naming
    def test_fails_for_none(self):
        D = CommonOfConcreteValidationTest.D[1:]

        msg = "'value' must not be None"

        with self.assertRaises(TypeError) as cm:
            D().validate(None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            D(required=False).validate(None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            D().validate([None])
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            D(required=False).validate([None])
        self.assertEqual(msg, str(cm.exception))

    def test_validate_with_multiplicity_mismatch_fails_with_meaningful_message(self):
        d = CommonOfConcreteValidationTest.D[1:]()
        with self.assertRaises(ValueError) as cm:
            d.validate([])
        msg = 'value has 0 members, which is not accepted according to the specified multiplicity [1:]'
        self.assertEqual(msg, str(cm.exception))

    def test_duplicate_free_cannot_contain_duplicates(self):
        paths = ['1', '2', '1']
        CommonOfConcreteValidationTest.D[:](unique=False).validate(paths)
        with self.assertRaises(ValueError) as cm:
            CommonOfConcreteValidationTest.D[:](unique=True).validate(paths)
        msg = "sequence of dependencies must be duplicate-free, but contains Path('1') more than once"
        self.assertEqual(str(cm.exception), msg)

    def test_value_must_be_iterable(self):
        with self.assertRaises(TypeError) as cm:
            CommonOfConcreteValidationTest.D[:]().validate(1)
        msg = "'int' object is not iterable"
        self.assertEqual(str(cm.exception), msg)

    def test_validate_with_str_of_bytes_fails_with_meaningful_message(self):
        msg = "since dependency has a multiplicity, value must be iterable (other than 'str' or 'bytes')"
        d = CommonOfConcreteValidationTest.D[:]()

        with self.assertRaises(TypeError) as cm:
            d.validate('')
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            d.validate(b'')
        self.assertEqual(msg, str(cm.exception))

    def test_each_member_is_validated(self):
        with self.assertRaises(ValueError):
            CommonOfConcreteValidationTest.D[:]().validate(['a', 'b/'])
        with self.assertRaises(ValueError):
            CommonOfConcreteValidationTest.D[:]().validate(['a/', 'b'])

    def test_member_count_must_match_multiplicity(self):
        with self.assertRaises(ValueError) as cm:
            CommonOfConcreteValidationTest.D[2:]().validate([])
        msg = "value has 0 members, which is not accepted according to the specified multiplicity [2:]"
        self.assertEqual(str(cm.exception), msg)


class CommonOfConcreteFilesystemObjectTest(unittest.TestCase):

    def test_fails_for_nonpath_cls(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.Tool.Input.RegularFile(cls=str)
        msg = "'cls' is not a subclass of 'dlb.fs.Path'"
        self.assertEqual(str(cm.exception), msg)

    def test_value_is_path(self):
        for c in filesystem_dependency_classes:
            self.assertIs(c.Value, dlb.fs.Path, repr(c))


class AbstractDependencyValidationTest(unittest.TestCase):

    def test_fails_with_meaningful_message(self):
        msg_tmpl = (
            "<class {!r}> is an abstract dependency class\n"
            "  | use one of its documented subclasses instead"
        )

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.Tool.Dependency().validate(0)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.Tool.Dependency'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.Tool.Input().validate(0)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.Tool.Input'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.Tool.Output().validate(0)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.Tool.Output'))


class SingleInputValidationTest(unittest.TestCase):

    def test_fails_for_none(self):
        msg = "'value' must not be None"

        with self.assertRaises(TypeError) as cm:
            dlb.ex.depend.RegularFileInput().validate(None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.ex.depend.RegularFileInput(required=False).validate(None)
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_invalid_path_conversion(self):
        with self.assertRaises(ValueError):
            dlb.ex.depend.RegularFileInput(cls=dlb.fs.NoSpacePath).validate('a /b')

    def test_regular_file_returns_path(self):
        v = dlb.ex.depend.RegularFileInput(cls=dlb.fs.NoSpacePath).validate('a/b')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_nonregular_file_returns_path(self):
        v = dlb.ex.depend.NonRegularFileInput(cls=dlb.fs.NoSpacePath).validate('a/b')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_directory_returns_path(self):
        v = dlb.ex.depend.DirectoryInput(cls=dlb.fs.NoSpacePath).validate('a/b/')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b/'))

    def test_envvar_returns_str_or_dict(self):
        d = dlb.ex.depend.EnvVarInput(name='number', restriction=r'[0-9]+[a-z]+', example='42s')
        self.assertEqual('123mm', d.validate('123mm'))

        d = dlb.ex.depend.EnvVarInput(
            name='number',
            restriction=r'(?P<num>[0-9]+)(?P<unit>[a-z]+)', example='42s')

        self.assertEqual({'num': '123', 'unit': 'mm'}, d.validate('123mm'))

        with self.assertRaises(TypeError) as cm:
            d.validate(b'')
        self.assertEqual(str(cm.exception), "'value' must be a str")

        with self.assertRaises(ValueError) as cm:
            d.validate('')
        self.assertEqual(str(cm.exception), "'value' must not be empty")


class PropertyTest(unittest.TestCase):

    def test_filesystem_input_dependency_has_cls(self):
        d = dlb.ex.depend.RegularFileInput()
        self.assertIs(d.cls, dlb.fs.Path)

        d = dlb.ex.depend.RegularFileInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.depend.NonRegularFileInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.depend.DirectoryInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

    def test_filesystem_output_dependency_has_cls(self):
        d = dlb.ex.depend.RegularFileOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.depend.NonRegularFileOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.depend.DirectoryOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

    def test_regularfile_output_dependency_has_replace_by_same_content(self):
        d = dlb.ex.depend.RegularFileOutput(replace_by_same_content=False)
        self.assertFalse(d.replace_by_same_content)

    def test_envvar_intput_dependency_has_name_restriction_and_example(self):
        d = dlb.ex.depend.EnvVarInput(name='n', restriction=r'.', example='!')
        self.assertEqual('n', d.name)
        self.assertEqual(re.compile(r'.'), d.restriction)
        self.assertEqual('!', d.example)


class FileInputValidationTest(unittest.TestCase):

    def test_fails_for_directory(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.RegularFileInput().validate('a/b/')
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")

        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.NonRegularFileInput().validate('a/b/')
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")


class DirectoryInputValidationTest(unittest.TestCase):

    def test_fails_for_file(self):

        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.DirectoryInput().validate('a/b')
        self.assertEqual(str(cm.exception), "non-directory path not valid for directory dependency: Path('a/b')")


class EnvVarInputValidationTest(unittest.TestCase):

    def test_fails_if_name_not_str(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.depend.EnvVarInput(name=1, restriction=r'[0-9]+', example='42')
        self.assertEqual(str(cm.exception), "'name' must be a str")

    def test_fails_if_name_empty(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.EnvVarInput(name='', restriction=r'[0-9]+', example='42')
        self.assertEqual(str(cm.exception), "'name' must not be empty")

    def test_fails_if_restriction_is_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.depend.EnvVarInput(name='number', restriction=b'42', example='42')
        self.assertEqual(str(cm.exception), "'restriction' must be regular expression (compiled or str)")

    def test_fails_if_example_is_none(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.depend.EnvVarInput(name='number', restriction='42', example=None)
        self.assertEqual(str(cm.exception), "'example' must be a str")

    def test_fails_with_nonmatching_example(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.EnvVarInput(name='number', restriction=r'[0-9]+', example='42s')
        self.assertEqual(str(cm.exception), "'example' is invalid with respect to 'restriction': '42s'")

    def test_invalid_if_value_does_not_match_all_the_value(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.EnvVarInput(name='number', restriction=r'[0-9]+[a-z]+', example='42s').validate('123mm2')
        msg = "value is invalid with respect to restriction: '123mm2'"
        self.assertEqual(str(cm.exception), msg)

    def test_fails_with_multiplicity(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.EnvVarInput[1](name='number', restriction=r'[0-9]+', example='42')
        self.assertEqual(str(cm.exception), "must not have a multiplicity")


class SingleOutputValidationTest(unittest.TestCase):

    def test_fail_for_none(self):
        msg = "'value' must not be None"

        with self.assertRaises(TypeError) as cm:
            dlb.ex.depend.RegularFileOutput().validate(None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.ex.depend.RegularFileOutput(required=False).validate(None)
        self.assertEqual(msg, str(cm.exception))

    def test_regular_file_returns_path(self):
        v = dlb.ex.depend.RegularFileOutput(cls=dlb.fs.NoSpacePath).validate('a/b')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_nonregular_file_returns_path(self):
        v = dlb.ex.depend.NonRegularFileOutput(cls=dlb.fs.NoSpacePath).validate('a/b')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_directory_returns_path(self):
        v = dlb.ex.depend.DirectoryOutput(cls=dlb.fs.NoSpacePath).validate('a/b/')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b/'))


# noinspection PyPep8Naming
class TupleFromValueTest(unittest.TestCase):

    def test_returns_none_or_tuple(self):
        D = dlb.ex.depend.RegularFileInput(required=False)

        self.assertEqual((), D.tuple_from_value(None))

        self.assertEqual((dlb.fs.Path('a/b'),), D.tuple_from_value(D.validate('a/b')))

        D = dlb.ex.depend.RegularFileInput[:]()
        self.assertEqual((dlb.fs.Path('a/b'),), D.tuple_from_value(D.validate(['a/b'])))
        self.assertEqual((dlb.fs.Path('a/b'), dlb.fs.Path('c'),), D.tuple_from_value(D.validate(['a/b', 'c'])))


# noinspection PyPep8Naming
class CompatibilityTest(unittest.TestCase):

    def test_is_compatible_to_self(self):
        for D in filesystem_dependency_classes:
            self.assertTrue(D().compatible_and_no_less_restrictive(D()))

        d1 = dlb.ex.depend.EnvVarInput(name='n', restriction=r'.*', example='')
        d2 = dlb.ex.depend.EnvVarInput(name='n', restriction=r'.*', example='')
        self.assertTrue(d1.compatible_and_no_less_restrictive(d2))

    def test_different_dependency_classes_are_not_compatible(self):
        A = dlb.ex.depend.RegularFileInput
        B = dlb.ex.depend.NonRegularFileInput
        self.assertFalse(A().compatible_and_no_less_restrictive(B()))

    def test_single_and_nonsingle_multiplicity_are_not_compatible(self):
        A = dlb.ex.depend.RegularFileInput
        B = dlb.ex.depend.RegularFileInput[:]
        self.assertFalse(B().compatible_and_no_less_restrictive(A()))

    def test_smaller_multiplicity_with_same_step_is_compatible(self):
        A = dlb.ex.depend.RegularFileInput[1:5]
        B = dlb.ex.depend.RegularFileInput[2:4]
        self.assertFalse(A().compatible_and_no_less_restrictive(B()))
        self.assertTrue(B().compatible_and_no_less_restrictive(A()))

    def test_multiplicity_with_different_step_is_not_compatible(self):
        A = dlb.ex.depend.RegularFileInput[1:5]
        B = dlb.ex.depend.RegularFileInput[1:5:2]
        self.assertFalse(A().compatible_and_no_less_restrictive(B()))
        self.assertFalse(B().compatible_and_no_less_restrictive(A()))

    def test_different_explicit_are_not_compatible(self):
        C = dlb.ex.depend.RegularFileInput
        self.assertFalse(C().compatible_and_no_less_restrictive(C(explicit=False)))
        self.assertFalse(C(explicit=False).compatible_and_no_less_restrictive(C()))

    def test_required_is_more_restrictive_than_notrequired(self):
        C = dlb.ex.depend.RegularFileInput
        self.assertTrue(C().compatible_and_no_less_restrictive(C(required=False)))
        self.assertFalse(C(required=False).compatible_and_no_less_restrictive(C()))

    def test_unique_is_more_restrictive_than_notunique(self):
        C = dlb.ex.depend.RegularFileInput
        self.assertTrue(C().compatible_and_no_less_restrictive(C(unique=False)))
        self.assertFalse(C(unique=False).compatible_and_no_less_restrictive(C()))

    def test_envvar_and_file_are_not_compatible(self):
        d1 = dlb.ex.depend.RegularFileInput()
        d2 = dlb.ex.depend.EnvVarInput(name='n1', restriction=r'.*', example='')
        self.assertFalse(d1.compatible_and_no_less_restrictive(d2))
        self.assertFalse(d2.compatible_and_no_less_restrictive(d1))

    def test_envvar_with_different_names_are_not_compatible(self):
        d1 = dlb.ex.depend.EnvVarInput(name='n1', restriction=r'.*', example='')
        d2 = dlb.ex.depend.EnvVarInput(name='n2', restriction=r'.*', example='')
        self.assertFalse(d1.compatible_and_no_less_restrictive(d2))
        self.assertFalse(d2.compatible_and_no_less_restrictive(d1))

    def test_envvar_with_different_restrictions_are_not_compatible(self):
        d1 = dlb.ex.depend.EnvVarInput(name='n', restriction=r'', example='')
        d2 = dlb.ex.depend.EnvVarInput(name='n', restriction=r'.*', example='')
        self.assertFalse(d1.compatible_and_no_less_restrictive(d2))
        self.assertFalse(d2.compatible_and_no_less_restrictive(d1))


class ValueOfNonAbstractDependencyTest(unittest.TestCase):

    def test_each_public_nonabstract_dependency_has_value(self):
        abstract_dependencies = (
            dlb.ex.depend.Input,
            dlb.ex.depend.Output
        )

        public_dependency_classes_except_abstract_ones = {
            v for n, v in dlb.ex.depend.__dict__.items() \
            if isinstance(v, type) and issubclass(v, dlb.ex.depend.Dependency) and
               v is not dlb.ex.depend.Dependency and not n.startswith('_') and
               v not in abstract_dependencies
        }

        for v in public_dependency_classes_except_abstract_ones:
            self.assertTrue(hasattr(v, 'Value'), repr(v))


class CoverageTest(unittest.TestCase):
    def test_all_concrete_dependency_is_complete(self):
        public_dependency_classes_except_abstract_ones = {
            v  for n, v in dlb.ex.depend.__dict__.items() \
            if isinstance(v, type) and issubclass(v, dlb.ex.depend.Dependency) and
               v is not dlb.ex.depend.Dependency and not n.startswith('_')
        }

        covered_concrete_dependencies = filesystem_dependency_classes + (dlb.ex.depend.EnvVarInput,)

        covered_abstract_dependencies = (
            dlb.ex.depend.Input,
            dlb.ex.depend.Output
        )

        # make sure no concrete dependency class is added to dlb.ex.depend without a test here
        self.assertEqual(set(covered_concrete_dependencies) | set(covered_abstract_dependencies),
                         public_dependency_classes_except_abstract_ones)
