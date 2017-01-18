import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

from dlb.cmd.tool import Tool, PropagatedEnvVar
import re
import os
import unittest


class InheritanceTest(unittest.TestCase):

    def test_hierarchy_matches_nesting(self):
        self.assertTrue(issubclass(Tool.Input, Tool.DependencyRole))
        self.assertTrue(issubclass(Tool.Input.RegularFile, Tool.Input))

        self.assertTrue(issubclass(Tool.Output, Tool.DependencyRole))
        self.assertTrue(issubclass(Tool.Output.RegularFile, Tool.Output))

    def test_multiplicity_inherits_nonconcrete_base(self):
        self.assertTrue(issubclass(Tool.Input.Directory[:], Tool.Input))
        self.assertFalse(issubclass(Tool.Input.Directory[:], Tool.Input.Directory))
        self.assertTrue(issubclass(Tool.Output.Directory[:], Tool.Output))
        self.assertFalse(issubclass(Tool.Output.Directory[:], Tool.Output.Directory))


# noinspection PyPep8Naming
class ReprTest(unittest.TestCase):

    def test_name_matches_class(self):
        self.assertEqual(Tool.DependencyRole.__name__, 'DependencyRole')
        self.assertEqual(Tool.Input.__name__, 'Input')

    def test_name_matches_nesting(self):
        self.assertEqual(repr(Tool.DependencyRole), "<class 'dlb.cmd.tool.Tool.DependencyRole'>")
        self.assertEqual(repr(Tool.Input), "<class 'dlb.cmd.tool.Tool.Input'>")
        self.assertEqual(repr(Tool.Input.RegularFile), "<class 'dlb.cmd.tool.Tool.Input.RegularFile'>")
        self.assertEqual(repr(Tool.Output), "<class 'dlb.cmd.tool.Tool.Output'>")
        self.assertEqual(repr(Tool.Output.RegularFile), "<class 'dlb.cmd.tool.Tool.Output.RegularFile'>")
        self.assertEqual(repr(Tool.Intermediate), "<class 'dlb.cmd.tool.Tool.Intermediate'>")

    def test_name_contains_multiplicity(self):
        D = Tool.Input.Directory
        self.assertEqual(D[:].__name__, 'Directory[:]')
        self.assertEqual(D[:].__qualname__, 'Tool.Input.Directory[:]')

        self.assertEqual(D[2:].__name__, 'Directory[2:]')
        self.assertEqual(D[:2].__name__, 'Directory[:2]')
        self.assertEqual(D[10:20:2].__name__, 'Directory[10:19:2]')
        self.assertEqual(D[2].__name__, 'Directory[2]')


class ValidationWithoutMultiplicityTest(unittest.TestCase):

    def test_abstract_dependency_cannot_be_validated(self):
        with self.assertRaises(AttributeError):
            Tool.Dependency().validate(0)
        with self.assertRaises(AttributeError):
            Tool.Input().validate(0)
        with self.assertRaises(AttributeError):
            Tool.Intermediate().validate(0)
        with self.assertRaises(AttributeError):
            Tool.Output().validate(0)

    def test_non_is_not_valid_for_required(self):
        self.assertIsNone(Tool.Input.RegularFile(required=False).validate(None))
        with self.assertRaises(ValueError) as cm:
            Tool.Input.RegularFile(required=True).validate(None)
        self.assertEqual(str(cm.exception), 'required dependency must not be None')

        self.assertIsNone(Tool.Output.Directory(required=False).validate(None))
        with self.assertRaises(ValueError) as cm:
            Tool.Output.Directory(required=True).validate(None)
        self.assertEqual(str(cm.exception), 'required dependency must not be None')

    def test_path_dependency_returns_path(self):
        import dlb.fs

        self.assertEqual(Tool.Input.RegularFile().validate('a/b'), dlb.fs.Path('a/b'))
        self.assertEqual(Tool.Input.Directory().validate('a/b/'), dlb.fs.Path('a/b/'))

        self.assertEqual(Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath).validate('a/b'), dlb.fs.NoSpacePath('a/b'))
        with self.assertRaises(ValueError):
            Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath).validate('a /b')

    def test_dir_is_not_valid_for_non_dir_dependency(self):
        with self.assertRaises(ValueError) as cm:
            Tool.Input.RegularFile().validate('a/b/')
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")

        with self.assertRaises(ValueError) as cm:
            Tool.Input.Directory().validate('a/b')
        self.assertEqual(str(cm.exception), "non-directory path not valid for directory dependency: Path('a/b')")

    def test_path_dependency_initialized_to_notimplemented(self):
        self.assertIs(Tool.Input.RegularFile().initial(), NotImplemented)

    def test_envvar_initial_is_from_environ(self):
        os.environ['XYZ'] = 'abc'
        self.assertEqual(Tool.Input.EnvVar(name='XYZ').initial(), 'abc')

    def test_envvar_regex_validator_requires_fullmatch(self):
        with self.assertRaises(ValueError) as cm:
            Tool.Input.EnvVar(name='XYZ', validator='b').validate('abc')
        self.assertEqual(str(cm.exception), "value does not match validator regular expression: 'abc'")

    def test_envvar_regex_validator_selects_group(self):
        self.assertEqual(Tool.Input.EnvVar(name='XYZ', validator=None).validate('abc'), 'abc')
        self.assertEqual(Tool.Input.EnvVar(name='XYZ', validator='.(?P<beta>.)(?P<alpha>.)').validate('abc'), 'c')
        self.assertEqual(Tool.Input.EnvVar(name='XYZ', validator=re.compile('.(.)(.)')).validate('abc'), 'b')
        self.assertEqual(Tool.Input.EnvVar(name='XYZ', validator='.{3}').validate('abc'), 'abc')
        self.assertIsNone(Tool.Input.EnvVar(name='XYZ', validator='.{3}', required=None).validate(None))

    def test_envvar_callable_validator_mast_not_raise(self):
        def validator(value):
            return int(value, 10)
        with self.assertRaises(ValueError):
            Tool.Input.EnvVar(name='XYZ', validator=validator).validate('abc')

    def test_envvar_callable_validator_selects_return_value(self):
        def validator(value):
            return int(value, 16)
        self.assertEqual(Tool.Input.EnvVar(name='XYZ', validator=validator).validate('cafe'), 51966)

    def test_propagated_envvar_value_is_unchanged(self):
        self.assertEqual(
            Tool.Input.EnvVar(name='XYZ', propagate=True, validator='.(.)(.)').validate('abc'),
            PropagatedEnvVar(name='XYZ', value='abc'))
        self.assertEqual(
            Tool.Input.EnvVar(name='XYZ', propagate=True, validator='.(.)(.)', required=False).validate(None),
            PropagatedEnvVar(name='XYZ', value=None))
        self.assertEqual(
            Tool.Input.EnvVar(name='XYZ', propagate=True, validator=lambda v: 123).validate('abc'),
            PropagatedEnvVar(name='XYZ', value='abc'))


# noinspection PyPep8Naming
class ValidationWithMultiplicityTest(unittest.TestCase):

    def test_value_must_be_iterable(self):
        D = Tool.Input.Directory

        with self.assertRaises(TypeError):
            D[:]().validate(1)

        with self.assertRaises(TypeError) as cm:
            D[:]().validate('abc')
        self.assertEqual(
            str(cm.exception),
            'since dependency role has a multiplicity, value must be iterable (other than string)')

    def test_member_count_must_match_multiplicity(self):
        D = Tool.Input.Directory

        with self.assertRaises(ValueError) as cm:
            D[2:]().validate([])
        self.assertEqual(
            str(cm.exception),
            'value has 0 members, but minimum multiplicity is 2')

        with self.assertRaises(ValueError) as cm:
            D[0:4:2]().validate(['1/', '2/', '3/'])
        self.assertEqual(
            str(cm.exception),
            'value has 3 members, but maximum multiplicity is 2')

        with self.assertRaises(ValueError) as cm:
            D[1::2]().validate(['1/', '2/'])
        self.assertEqual(
            str(cm.exception),
            'value has 2 members, but multiplicity must be an integer multiple of 2 above 1')

    def test_each_member_is_validated(self):
        D = Tool.Input.Directory

        with self.assertRaises(ValueError):
            D[:]().validate(['a', 'b/'])
        with self.assertRaises(ValueError):
            D[:]().validate(['a/', 'b'])

    def test_member_must_not_be_none_even_if_dependency_role_not_required(self):
        D = Tool.Input.Directory
        with self.assertRaises(ValueError) as cm:
            D[:](required=False).validate([None])
        self.assertEqual(str(cm.exception), 'required dependency must not be None')

    def test_duplicate_free_cannot_contain_duplicates(self):
        D = Tool.Input.Directory
        paths = ['1/', '2/', '1/']
        D[:](unique=False).validate(paths)
        with self.assertRaises(ValueError) as cm:
            D[:](unique=True).validate(paths)
        self.assertEqual(str(cm.exception), "dependency must be duplicate-free, but contains Path('1/') more than once")


# noinspection PyPep8Naming
class MultiplicityTest(unittest.TestCase):

    def test_no_multiplicity(self):
        D = Tool.Input.Directory
        self.assertIsNone(D.multiplicity)

        self.assertTrue(D.is_multiplicity_valid(None))
        self.assertFalse(D.is_multiplicity_valid(0))
        self.assertFalse(D.is_multiplicity_valid(1))

    def test_int_multiplicity(self):
        D = Tool.Input.Directory

        M = D[0]
        self.assertFalse(M.is_multiplicity_valid(-1))
        self.assertTrue(M.is_multiplicity_valid(0))
        self.assertFalse(M.is_multiplicity_valid(1))

        M = D[100]
        self.assertFalse(M.is_multiplicity_valid(99))
        self.assertTrue(M.is_multiplicity_valid(100))
        self.assertFalse(M.is_multiplicity_valid(101))

    def test_slice_multiplicity(self):
        D = Tool.Input.Directory

        M = D[2:]
        self.assertFalse(M.is_multiplicity_valid(1))
        self.assertTrue(M.is_multiplicity_valid(2))
        self.assertTrue(M.is_multiplicity_valid(3))

        M = D[:2]
        self.assertTrue(M.is_multiplicity_valid(0))
        self.assertTrue(M.is_multiplicity_valid(1))
        self.assertFalse(M.is_multiplicity_valid(2))

        M = D[:]
        self.assertTrue(M.is_multiplicity_valid(0))
        self.assertTrue(M.is_multiplicity_valid(1))
        self.assertTrue(M.is_multiplicity_valid(100))

        M = D[1::5]
        self.assertFalse(M.is_multiplicity_valid(0))
        self.assertTrue(M.is_multiplicity_valid(1))
        self.assertFalse(M.is_multiplicity_valid(2))
        self.assertFalse(M.is_multiplicity_valid(5))
        self.assertTrue(M.is_multiplicity_valid(6))
        self.assertFalse(M.is_multiplicity_valid(7))

    def test_nonint_multiplicity(self):
        D = Tool.Input.Directory
        with self.assertRaises(TypeError) as cm:
            D[:].is_multiplicity_valid('')
        self.assertEqual(str(cm.exception), 'multiplicity must be None or integer')

    def test_is_normalized(self):
        D = Tool.Input.Directory

        self.assertEqual(
            D[:].multiplicity,
            D[0::].multiplicity)

        self.assertEqual(
            D[2].multiplicity,
            D[2:3].multiplicity)

        self.assertEqual(
            D[100:0].multiplicity,
            D[0].multiplicity)

        self.assertEqual(
            D[10:15:10].multiplicity,
            D[10].multiplicity)

        self.assertEqual(
            D[10:55:10].multiplicity,
            D[10:51:10].multiplicity)

    def test_is_same_on_class_and_instance(self):
        D = Tool.Input.Directory
        self.assertEqual(D.multiplicity, D().multiplicity)

    def test_cannot_be_nested(self):
        D = Tool.Input.Directory
        with self.assertRaises(TypeError) as cm:
            # noinspection PyStatementEffect
            D[:][:]
        self.assertEqual(str(cm.exception), 'dependency role with multiplicity is not subscriptable')

    def test_classes_for_same_multiplicity_are_identical(self):
        D = Tool.Input.Directory
        self.assertIs(D[:], D[:])
        self.assertIs(D[1], D[1:2])
        self.assertTrue(issubclass(D[:], D[:]))
