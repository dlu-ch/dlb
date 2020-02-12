import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex.mult
import dlb.ex.depend
import re
import unittest
import tools_for_test


class DependencyTest(unittest.TestCase):

    def test_is_multiplicity_holder(self):
        d = dlb.ex.depend.Dependency()
        self.assertIsInstance(d, dlb.ex.mult.MultiplicityHolder)

    def test_validate_fail_with_meaningful_message(self):
        msg = (
            "<class 'dlb.ex.Tool.Dependency'> is abstract\n"
            "  | use one of its documented subclasses instead"
        )

        d = dlb.ex.depend.Dependency()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate('', None)
        self.assertEqual(msg, str(cm.exception))

        d = dlb.ex.depend.Dependency[:]()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate([1], None)
        self.assertEqual(msg, str(cm.exception))


class CommonOfNonAbstractDependencyTest(unittest.TestCase):

    # stands for any non-abstract subclass of Dependency:
    D = dlb.ex.depend.RegularFileInput

    def test_validate_with_multiplicity_mismatch_fails_with_meaningful_message(self):
        d = CommonOfNonAbstractDependencyTest.D[1:]()
        with self.assertRaises(ValueError) as cm:
            d.validate([], None)
        msg = 'value has 0 members, which is not accepted according to the specified multiplicity [1:]'
        self.assertEqual(msg, str(cm.exception))

    def test_duplicate_free_cannot_contain_duplicates(self):
        paths = ['1', '2', '1']
        CommonOfNonAbstractDependencyTest.D[:](unique=False).validate(paths, None)
        with self.assertRaises(ValueError) as cm:
            CommonOfNonAbstractDependencyTest.D[:](unique=True).validate(paths, None)
        msg = "sequence of dependencies must be duplicate-free, but contains Path('1') more than once"
        self.assertEqual(str(cm.exception), msg)

    def test_value_must_be_iterable(self):
        with self.assertRaises(TypeError) as cm:
            CommonOfNonAbstractDependencyTest.D[:]().validate(1, None)
        msg = "'int' object is not iterable"
        self.assertEqual(str(cm.exception), msg)

    def test_validate_with_str_of_bytes_fails_with_meaningful_message(self):
        msg = "since dependency has a multiplicity, value must be iterable (other than 'str' or 'bytes')"
        d = CommonOfNonAbstractDependencyTest.D[:]()

        with self.assertRaises(TypeError) as cm:
            d.validate('', None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            d.validate(b'', None)
        self.assertEqual(msg, str(cm.exception))

    def test_each_member_is_validated(self):
        with self.assertRaises(ValueError):
            CommonOfNonAbstractDependencyTest.D[:]().validate(['a', 'b/'], None)
        with self.assertRaises(ValueError):
            CommonOfNonAbstractDependencyTest.D[:]().validate(['a/', 'b'], None)

    def test_member_count_must_match_multiplicity(self):
        with self.assertRaises(ValueError) as cm:
            CommonOfNonAbstractDependencyTest.D[2:]().validate([], None)
        msg = "value has 0 members, which is not accepted according to the specified multiplicity [2:]"
        self.assertEqual(str(cm.exception), msg)


class AbstractDependencyClassesTest(unittest.TestCase):

    def test_fails_with_meaningful_message(self):
        msg_tmpl = (
            "<class {!r}> is abstract\n"
            "  | use one of its documented subclasses instead"
        )

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.Tool.Dependency().validate(0, None)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.Tool.Dependency'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.Tool.Input().validate(0, None)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.Tool.Input'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.Tool.Intermediate().validate(0, None)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.Tool.Intermediate'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.Tool.Output().validate(0, None)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.Tool.Output'))


class SingleInputTypeTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_none(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.depend.RegularFileInput().validate(None, None)
        self.assertEqual(str(cm.exception), "'value' must not be None")

    def test_fails_for_invalid_path_conversion(self):
        with self.assertRaises(ValueError):
            dlb.ex.depend.RegularFileInput(cls=dlb.fs.NoSpacePath).validate('a /b', None)

    def test_regular_file_returns_path(self):
        v = dlb.ex.depend.RegularFileInput(cls=dlb.fs.NoSpacePath).validate('a/b', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_nonregular_file_returns_path(self):
        v = dlb.ex.depend.NonRegularFileInput(cls=dlb.fs.NoSpacePath).validate('a/b', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_directory_returns_path(self):
        v = dlb.ex.depend.DirectoryInput(cls=dlb.fs.NoSpacePath).validate('a/b/', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b/'))

    def test_envvar_returns_str_or_dict(self):
        os.mkdir('.dlbroot')

        try:
            del os.environ['UV']
        except KeyError:
            pass

        with dlb.ex.Context() as c:
            c.env.import_from_outer('UV', r'.*', '')
            c.env['UV'] = '123mm'

            v = dlb.ex.depend.EnvVarInput(
                restriction=r'[0-9]+[a-z]+', example='42s').validate('UV', c)
            self.assertEqual(v, '123mm')

            v = dlb.ex.depend.EnvVarInput(
                restriction=r'(?P<num>[0-9]+)(?P<unit>[a-z]+)', example='42s').validate('UV', c)
            self.assertEqual(v, {'num': '123', 'unit': 'mm'})


class InputPropertyTest(unittest.TestCase):

    def test_filesystem_input_dependency_has_cls_and_(self):
        d = dlb.ex.depend.RegularFileInput()
        self.assertIs(d.cls, dlb.fs.Path)
        self.assertTrue(d.ignore_permission)

        d = dlb.ex.depend.RegularFileInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)
        d = dlb.ex.depend.RegularFileInput(ignore_permission=False)
        self.assertFalse(d.ignore_permission)

        d = dlb.ex.depend.NonRegularFileInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)
        d = dlb.ex.depend.RegularFileInput(ignore_permission=False)
        self.assertFalse(d.ignore_permission)

        d = dlb.ex.depend.DirectoryInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)
        d = dlb.ex.depend.RegularFileInput(ignore_permission=False)
        self.assertFalse(d.ignore_permission)

    def test_filesystem_output_dependency_has_cls(self):

        d = dlb.ex.depend.RegularFileOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.depend.NonRegularFileOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.depend.DirectoryOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

    def test_envvar_intput_dependency_has_restriction_example(self):
        d = dlb.ex.depend.EnvVarInput(restriction=r'.', example='!')
        self.assertEqual(re.compile(r'.'), d.restriction)
        self.assertEqual('!', d.example)


class FileInputValidationTest(unittest.TestCase):

    def test_fails_for_directory(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.RegularFileInput().validate('a/b/', None)
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")

        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.NonRegularFileInput().validate('a/b/', None)
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")


class DirectoryInputValidationTest(unittest.TestCase):

    def test_fails_for_fil(self):

        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.DirectoryInput().validate('a/b', None)
        self.assertEqual(str(cm.exception), "non-directory path not valid for directory dependency: Path('a/b')")


class EnvVarInputValidationTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_with_nonmatching_example(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.depend.EnvVarInput(restriction=r'[0-9]+', example='42s')
        self.assertEqual(str(cm.exception), "'example' is invalid with respect to 'restriction': '42s'")

    def test_fails_without_context(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.depend.EnvVarInput(restriction=r'[0-9]+[a-z]+', example='42s').validate('UV', None)
        self.assertEqual(str(cm.exception), "needs context")

    def test_restriction_matches_all(self):
        os.mkdir('.dlbroot')

        try:
            del os.environ['UV']
        except KeyError:
            pass

        with dlb.ex.Context() as c:
            c.env.import_from_outer('UV', r'.*', '')
            c.env['UV'] = '123mm2'

            with self.assertRaises(ValueError) as cm:
                dlb.ex.depend.EnvVarInput(restriction=r'[0-9]+[a-z]+', example='42s').validate('UV', c)
            msg = "value of environment variable 'UV' is invalid with respect to restriction: '123mm2'"
            self.assertEqual(str(cm.exception), msg)

    def test_fail_on_undefined(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c:
            with self.assertRaises(ValueError) as cm:
                dlb.ex.depend.EnvVarInput(restriction=r'[0-9]+[a-z]+', example='42s').validate('UV', c)
            msg = (
                "not a defined environment variable in the context: 'UV'\n"
                "  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...]' = ..."
            )
            self.assertEqual(str(cm.exception), msg)


class SingleOutputTypeTest(unittest.TestCase):

    def test_fail_for_none(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.depend.RegularFileOutput().validate(None, None)
        self.assertEqual(str(cm.exception), "'value' must not be None")

    def test_regular_file_returns_path(self):
        v = dlb.ex.depend.RegularFileOutput(cls=dlb.fs.NoSpacePath).validate('a/b', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_nonregular_file_returns_path(self):
        v = dlb.ex.depend.NonRegularFileOutput(cls=dlb.fs.NoSpacePath).validate('a/b', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_directory_returns_path(self):
        v = dlb.ex.depend.DirectoryOutput(cls=dlb.fs.NoSpacePath).validate('a/b/', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b/'))


# noinspection PyPep8Naming
class CompatibilityTest:

    def test_is_compatible_to_self(self):
        Ds = [
            dlb.ex.depend.RegularFileInput,
            dlb.ex.depend.NonRegularFileInput,
            dlb.ex.depend.DirectoryInput,
            dlb.ex.depend.RegularFileOutput,
            dlb.ex.depend.NonRegularFileOutput,
            dlb.ex.depend.DirectoryOutput
        ]

        for D in Ds:
            self.assertTrue(D().compatible_and_no_less_restrictive(D()))

        d1 = dlb.ex.depend.EnvVarInput(restriction=r'.', example='')
        d2 = dlb.ex.depend.EnvVarInput(restriction=r'.', example='')
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
