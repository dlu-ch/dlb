# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex._mult
import dlb.ex._depend
import dlb.ex.input
import dlb.ex.output
import re
import inspect
import unittest
from typing import Tuple, Type


filesystem_dependency_classes: Tuple[Type[dlb.ex._depend.Dependency], ...] = (
    dlb.ex.input.RegularFile,
    dlb.ex.input.NonRegularFile,
    dlb.ex.input.Directory,
    dlb.ex.output.RegularFile,
    dlb.ex.output.NonRegularFile,
    dlb.ex.output.Directory
)


class ReprTest(unittest.TestCase):
    def test_reflects_module(self):
        self.assertEqual(repr(dlb.ex.Dependency), "<class 'dlb.ex.Dependency'>")
        self.assertEqual(repr(dlb.ex.InputDependency), "<class 'dlb.ex.InputDependency'>")
        self.assertEqual(repr(dlb.ex.OutputDependency), "<class 'dlb.ex.OutputDependency'>")
        self.assertEqual(repr(dlb.ex.input.RegularFile), "<class 'dlb.ex.input.RegularFile'>")
        self.assertEqual(repr(dlb.ex.output.RegularFile), "<class 'dlb.ex.output.RegularFile'>")


class InheritanceTest(unittest.TestCase):

    def test_abstract(self):
        self.assertTrue(issubclass(dlb.ex.InputDependency, dlb.ex.Dependency))
        self.assertTrue(issubclass(dlb.ex.OutputDependency, dlb.ex.Dependency))

    def test_all_in_input_are_input_dependencies(self):
        classes = {v for v in dlb.ex.input.__dict__.values() if inspect.isclass(v)}

        imported_classes = {v for v in classes if v.__module__ != 'dlb.ex.input'}
        unknown_imported_class_names = {v.__qualname__ for v in imported_classes}
        self.assertEqual(set(), unknown_imported_class_names)

        for v in classes - imported_classes:
            if inspect.isclass(v):
                self.assertTrue(issubclass(v, dlb.ex.InputDependency), repr(f"{v.__module__}.{v.__qualname__}"))

    def test_all_in_output_are_input_dependencies(self):
        classes = {v for v in dlb.ex.output.__dict__.values() if inspect.isclass(v)}

        imported_classes = {v for v in classes if v.__module__ != 'dlb.ex.output'}
        unknown_imported_class_names = {v.__qualname__ for v in imported_classes} - {'Any'}  # Python 3.11: Any
        self.assertEqual(set(), unknown_imported_class_names)

        for v in classes - imported_classes:
            if inspect.isclass(v):
                self.assertTrue(issubclass(v, dlb.ex.OutputDependency), repr(f"{v.__module__}.{v.__qualname__}"))


class BaseDependencyTest(unittest.TestCase):

    def test_is_multiplicity_holder(self):
        d = dlb.ex._depend.Dependency()
        self.assertIsInstance(d, dlb.ex._mult.MultiplicityHolder)

    def test_validate_fail_with_meaningful_message(self):
        msg = (
            "<class 'dlb.ex.Dependency'> is an abstract dependency class\n"
            "  | use one of its documented subclasses instead"
        )

        d = dlb.ex._depend.Dependency()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate('')
        self.assertEqual(msg, str(cm.exception))

        d = dlb.ex._depend.Dependency[:]()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate([1])
        self.assertEqual(msg, str(cm.exception))


class CommonOfConcreteValidationTest(unittest.TestCase):

    # stands for any non-abstract subclass of Dependency:
    D = dlb.ex.input.RegularFile

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
        with self.assertRaises(ValueError) as cm:
            CommonOfConcreteValidationTest.D[:]().validate(paths)
        msg = "iterable must be duplicate-free but contains Path('1') more than once"
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
            # noinspection PyTypeChecker
            dlb.ex.input.RegularFile(cls=str)
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
            dlb.ex.Dependency().validate(0)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.Dependency'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.InputDependency().validate(0)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.InputDependency'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.OutputDependency().validate(0)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.OutputDependency'))


class SingleInputValidationTest(unittest.TestCase):

    def test_fails_for_none(self):
        msg = "'value' must not be None"

        with self.assertRaises(TypeError) as cm:
            dlb.ex.input.RegularFile().validate(None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.ex.input.RegularFile(required=False).validate(None)
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_invalid_path_conversion(self):
        with self.assertRaises(ValueError):
            dlb.ex.input.RegularFile(cls=dlb.fs.NoSpacePath).validate('a /b')

    def test_regular_file_returns_path(self):
        v = dlb.ex.input.RegularFile(cls=dlb.fs.NoSpacePath).validate('a/b')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_nonregular_file_returns_path(self):
        v = dlb.ex.input.NonRegularFile(cls=dlb.fs.NoSpacePath).validate('a/b')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_directory_returns_path(self):
        v = dlb.ex.input.Directory(cls=dlb.fs.NoSpacePath).validate('a/b/')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b/'))

    def test_envvar_returns_str_or_dict(self):
        d = dlb.ex.input.EnvVar(name='number', pattern=r'[0-9]+[a-z]+', example='42s')
        # noinspection PyCallByClass
        self.assertEqual(dlb.ex.input.EnvVar.Value(name='number', raw='123mm', groups={}), d.validate('123mm'))

        d = dlb.ex.input.EnvVar(name='number', pattern=r'(?P<num>[0-9]+)(?P<unit>[a-z]+)', example='42s')

        # noinspection PyCallByClass
        self.assertEqual(dlb.ex.input.EnvVar.Value(name='number', raw='123mm', groups={'num': '123', 'unit': 'mm'}),
                         d.validate('123mm'))

        with self.assertRaises(TypeError) as cm:
            d.validate(b'')
        self.assertEqual(str(cm.exception), "'value' must be a str")


class PropertyTest(unittest.TestCase):

    def test_filesystem_input_dependency_has_cls(self):
        d = dlb.ex.input.RegularFile()
        self.assertIs(d.cls, dlb.fs.Path)

        d = dlb.ex.input.RegularFile(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.input.NonRegularFile(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.input.Directory(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

    def test_filesystem_output_dependency_has_cls(self):
        d = dlb.ex.output.RegularFile(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.output.NonRegularFile(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.output.Directory(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

    def test_regularfile_output_dependency_has_replace_by_same_content(self):
        d = dlb.ex.output.RegularFile(replace_by_same_content=False)
        self.assertFalse(d.replace_by_same_content)

    def test_envvar_intput_dependency_has_name_pattern_and_example(self):
        d = dlb.ex.input.EnvVar(name='n', pattern=r'.', example='!')
        self.assertEqual('n', d.name)
        self.assertEqual(re.compile(r'.'), d.pattern)
        self.assertEqual('!', d.example)


class FileInputValidationTest(unittest.TestCase):

    def test_fails_for_directory(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.input.RegularFile().validate('a/b/')
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")

        with self.assertRaises(ValueError) as cm:
            dlb.ex.input.NonRegularFile().validate('a/b/')
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")


class DirectoryInputValidationTest(unittest.TestCase):

    def test_fails_for_file(self):

        with self.assertRaises(ValueError) as cm:
            dlb.ex.input.Directory().validate('a/b')
        self.assertEqual(str(cm.exception), "non-directory path not valid for directory dependency: Path('a/b')")


class EnvVarInputValidationTest(unittest.TestCase):

    def test_fails_if_name_not_str(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.input.EnvVar(name=1, pattern=r'[0-9]+', example='42')
        self.assertEqual(str(cm.exception), "'name' must be a str")

    def test_fails_if_name_empty(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.input.EnvVar(name='', pattern=r'[0-9]+', example='42')
        self.assertEqual(str(cm.exception), "'name' must not be empty")

    def test_fails_if_pattern_is_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.input.EnvVar(name='number', pattern=b'42', example='42')
        self.assertEqual(str(cm.exception), "'pattern' must be regular expression (compiled or str)")

    def test_fails_if_example_is_none(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.input.EnvVar(name='number', pattern='42', example=None)
        self.assertEqual(str(cm.exception), "'example' must be a str")

    def test_fails_with_nonmatching_example(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.input.EnvVar(name='number', pattern=r'[0-9]+', example='42s')
        self.assertEqual(str(cm.exception), "'example' is not matched by 'pattern': '42s'")

    def test_invalid_if_value_does_not_match_all_the_value(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.input.EnvVar(name='number', pattern=r'[0-9]+[a-z]+', example='42s').validate('123mm2')
        msg = "value '123mm2' is not matched by validation pattern '[0-9]+[a-z]+'"
        self.assertEqual(str(cm.exception), msg)

    def test_fails_with_multiplicity(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.input.EnvVar[1](name='number', pattern=r'[0-9]+', example='42')
        self.assertEqual(str(cm.exception), "must not have a multiplicity")


class SingleOutputValidationTest(unittest.TestCase):

    def test_fail_for_none(self):
        msg = "'value' must not be None"

        with self.assertRaises(TypeError) as cm:
            dlb.ex.output.RegularFile().validate(None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.ex.output.RegularFile(required=False).validate(None)
        self.assertEqual(msg, str(cm.exception))

    def test_regular_file_returns_path(self):
        v = dlb.ex.output.RegularFile(cls=dlb.fs.NoSpacePath).validate('a/b')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_nonregular_file_returns_path(self):
        v = dlb.ex.output.NonRegularFile(cls=dlb.fs.NoSpacePath).validate('a/b')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_directory_returns_path(self):
        v = dlb.ex.output.Directory(cls=dlb.fs.NoSpacePath).validate('a/b/')
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b/'))


class ObjectOutputValidationTest(unittest.TestCase):

    def test_validated_value_is_equal_to_value(self):
        d = dlb.ex.output.Object(explicit=False)
        values = ['iu', 123.0, ({}, [None, dlb.fs.Path('42')])]
        for v in values:
            self.assertEqual(v, d.validate(v), repr(v))

    def test_validated_list_value_is_copy(self):
        d = dlb.ex.output.Object(explicit=False)
        li = [1, 2, 3]
        v = d.validate(li)
        li.append(4)
        self.assertEqual([1, 2, 3], v)

    def test_fails_for_none(self):
        d = dlb.ex.output.Object(explicit=False)
        with self.assertRaises(TypeError):
            d.validate(None)

    def test_fails_for_notimplemented(self):
        d = dlb.ex.output.Object(explicit=False)
        with self.assertRaises(ValueError) as cm:
            d.validate(NotImplemented)
        self.assertEqual(str(cm.exception), "value is invalid: NotImplemented")

    def test_fails_with_explicit(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.output.Object(explicit=True)
        self.assertEqual(str(cm.exception), "must not be explicit")


# noinspection PyPep8Naming
class TupleFromValueTest(unittest.TestCase):

    def test_returns_none_or_tuple(self):
        D = dlb.ex.input.RegularFile(required=False)

        self.assertEqual((), D.tuple_from_value(None))

        self.assertEqual((dlb.fs.Path('a/b'),), D.tuple_from_value(D.validate('a/b')))

        D = dlb.ex.input.RegularFile[:]()
        self.assertEqual((dlb.fs.Path('a/b'),), D.tuple_from_value(D.validate(['a/b'])))
        self.assertEqual((dlb.fs.Path('a/b'), dlb.fs.Path('c'),), D.tuple_from_value(D.validate(['a/b', 'c'])))


# noinspection PyPep8Naming
class CompatibilityTest(unittest.TestCase):

    def test_is_compatible_to_self(self):
        for D in filesystem_dependency_classes:
            self.assertTrue(D().compatible_and_no_less_restrictive(D()))

        d1 = dlb.ex.input.EnvVar(name='n', pattern=r'.*', example='')
        d2 = dlb.ex.input.EnvVar(name='n', pattern=r'.*', example='')
        self.assertTrue(d1.compatible_and_no_less_restrictive(d2))

        d1 = dlb.ex.output.Object(explicit=False)
        d2 = dlb.ex.output.Object(explicit=False)
        self.assertTrue(d1.compatible_and_no_less_restrictive(d2))

    def test_different_dependency_classes_are_not_compatible(self):
        A = dlb.ex.input.RegularFile
        B = dlb.ex.input.NonRegularFile
        self.assertFalse(A().compatible_and_no_less_restrictive(B()))

    def test_single_and_nonsingle_multiplicity_are_not_compatible(self):
        A = dlb.ex.input.RegularFile
        B = dlb.ex.input.RegularFile[:]
        self.assertFalse(B().compatible_and_no_less_restrictive(A()))

    def test_smaller_multiplicity_with_same_step_is_compatible(self):
        A = dlb.ex.input.RegularFile[1:5]
        B = dlb.ex.input.RegularFile[2:4]
        self.assertFalse(A().compatible_and_no_less_restrictive(B()))
        self.assertTrue(B().compatible_and_no_less_restrictive(A()))

    def test_multiplicity_with_different_step_is_not_compatible(self):
        A = dlb.ex.input.RegularFile[1:5]
        B = dlb.ex.input.RegularFile[1:5:2]
        self.assertFalse(A().compatible_and_no_less_restrictive(B()))
        self.assertFalse(B().compatible_and_no_less_restrictive(A()))

    def test_multiplicity_without_stop_less_restrictive_than_with_stop(self):
        A = dlb.ex.input.RegularFile[1:5]
        B = dlb.ex.input.RegularFile[1:]
        self.assertTrue(A().compatible_and_no_less_restrictive(B()))
        self.assertFalse(B().compatible_and_no_less_restrictive(A()))

    def test_multiplicity_with_larger_stop_less_restrictive(self):
        A = dlb.ex.input.RegularFile[1:5]
        B = dlb.ex.input.RegularFile[1:6]
        self.assertTrue(A().compatible_and_no_less_restrictive(B()))
        self.assertFalse(B().compatible_and_no_less_restrictive(A()))

    def test_different_explicit_are_not_compatible(self):
        C = dlb.ex.input.RegularFile
        self.assertFalse(C().compatible_and_no_less_restrictive(C(explicit=False)))
        self.assertFalse(C(explicit=False).compatible_and_no_less_restrictive(C()))

    def test_required_is_more_restrictive_than_notrequired(self):
        C = dlb.ex.input.RegularFile
        self.assertTrue(C().compatible_and_no_less_restrictive(C(required=False)))
        self.assertFalse(C(required=False).compatible_and_no_less_restrictive(C()))

    def test_envvar_and_file_are_not_compatible(self):
        d1 = dlb.ex.input.RegularFile()
        d2 = dlb.ex.input.EnvVar(name='n1', pattern=r'.*', example='')
        self.assertFalse(d1.compatible_and_no_less_restrictive(d2))
        self.assertFalse(d2.compatible_and_no_less_restrictive(d1))

    def test_envvar_with_different_names_are_not_compatible(self):
        d1 = dlb.ex.input.EnvVar(name='n1', pattern=r'.*', example='')
        d2 = dlb.ex.input.EnvVar(name='n2', pattern=r'.*', example='')
        self.assertFalse(d1.compatible_and_no_less_restrictive(d2))
        self.assertFalse(d2.compatible_and_no_less_restrictive(d1))

    def test_envvar_with_different_validation_patterns_are_not_compatible(self):
        d1 = dlb.ex.input.EnvVar(name='n', pattern=r'', example='')
        d2 = dlb.ex.input.EnvVar(name='n', pattern=r'.*', example='')
        self.assertFalse(d1.compatible_and_no_less_restrictive(d2))
        self.assertFalse(d2.compatible_and_no_less_restrictive(d1))


class ValueOfNonAbstractDependencyTest(unittest.TestCase):

    def test_each_public_nonabstract_dependency_has_value(self):
        abstract_dependencies = (
            dlb.ex._depend.InputDependency,
            dlb.ex._depend.OutputDependency
        )

        public_dependency_classes_except_abstract_ones = {
            v for n, v in dlb.ex._depend.__dict__.items()
            if (isinstance(v, type) and issubclass(v, dlb.ex._depend.Dependency) and
                v is not dlb.ex._depend.Dependency and not n.startswith('_') and v not in abstract_dependencies)
        }

        for v in public_dependency_classes_except_abstract_ones:
            self.assertTrue(hasattr(v, 'Value'), repr(v))


class CoverageTest(unittest.TestCase):
    def test_all_concrete_dependency_is_complete(self):
        public_dependency_classes_except_abstract_ones = {
            v for m in [dlb.ex._depend, dlb.ex.input, dlb.ex.output]
            for n, v in m.__dict__.items()
            if isinstance(v, type) and issubclass(v, dlb.ex._depend.Dependency)
        }

        covered_concrete_dependencies = filesystem_dependency_classes + (
            dlb.ex.input.EnvVar, dlb.ex.output.Object)

        covered_abstract_dependencies = (
            dlb.ex._depend.Dependency,
            dlb.ex._depend.InputDependency,
            dlb.ex._depend.OutputDependency
        )

        # make sure no concrete dependency class is added to dlb.ex._depend without a test here
        self.assertEqual(set(covered_concrete_dependencies) | set(covered_abstract_dependencies),
                         public_dependency_classes_except_abstract_ones)
