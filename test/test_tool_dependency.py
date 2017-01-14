import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

from dlb.cmd.tool import Tool
import unittest


class InheritanceTest(unittest.TestCase):

    def test_hierarchy_matches_nesting(self):
        self.assertTrue(issubclass(Tool.Input, Tool.Dependency))
        self.assertTrue(issubclass(Tool.Input.RegularFile, Tool.Input))

        self.assertTrue(issubclass(Tool.Output, Tool.Dependency))
        self.assertTrue(issubclass(Tool.Output.RegularFile, Tool.Output))


class ReprTest(unittest.TestCase):

    def test_name_matches_class(self):
        self.assertEqual(Tool.Dependency.__name__, 'Dependency')
        self.assertEqual(Tool.Input.__name__, 'Input')

    def test_name_matches_nesting(self):
        self.assertEqual(repr(Tool.Dependency), "<class 'dlb.cmd.tool.Tool.Dependency'>")
        self.assertEqual(repr(Tool.Input), "<class 'dlb.cmd.tool.Tool.Input'>")
        self.assertEqual(repr(Tool.Input.RegularFile), "<class 'dlb.cmd.tool.Tool.Input.RegularFile'>")
        self.assertEqual(repr(Tool.Output), "<class 'dlb.cmd.tool.Tool.Output'>")
        self.assertEqual(repr(Tool.Output.RegularFile), "<class 'dlb.cmd.tool.Tool.Output.RegularFile'>")
        self.assertEqual(repr(Tool.Intermediate), "<class 'dlb.cmd.tool.Tool.Intermediate'>")


class ValidationWithoutMultiplicityTest(unittest.TestCase):

    def test_abstract_dependency_validation_raises(self):
        with self.assertRaises(NotImplementedError):
            Tool.Dependency().validate(0)
        with self.assertRaises(NotImplementedError):
            Tool.Input().validate(0)
        with self.assertRaises(NotImplementedError):
            Tool.Intermediate().validate(0)
        with self.assertRaises(NotImplementedError):
            Tool.Output().validate(0)

    def test_non_is_not_valid_for_required(self):
        self.assertIsNone(Tool.Input.RegularFile(is_required=False).validate(None))
        with self.assertRaises(ValueError) as cm:
            Tool.Input.RegularFile(is_required=True).validate(None)
        self.assertEqual(str(cm.exception), 'required dependency must not be None')

        self.assertIsNone(Tool.Output.Directory(is_required=False).validate(None))
        with self.assertRaises(ValueError) as cm:
            Tool.Output.Directory(is_required=True).validate(None)
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


# noinspection PyPep8Naming
class ValidationWithMultiplicityTest(unittest.TestCase):

    def test_value_must_be_iterable(self):
        with self.assertRaises(TypeError):
            Tool.Dependency[:]().validate(1)

        with self.assertRaises(TypeError) as cm:
            Tool.Dependency[:]().validate('abc')
        self.assertEqual(
            str(cm.exception),
            'since dependency role has a multiplicity, value must be iterable (other than string)')

    def test_element_count_must_match_multiplicity(self):
        D = Tool.Input.RegularFile

        with self.assertRaises(ValueError) as cm:
            D[2:]().validate([])
        self.assertEqual(
            str(cm.exception),
            'value has 0 elements, but minimum multiplicity is 2')

        with self.assertRaises(ValueError) as cm:
            D[0:4:2]().validate(['1', '2', '3'])
        self.assertEqual(
            str(cm.exception),
            'value has 3 elements, but maximum multiplicity is 2')

        with self.assertRaises(ValueError) as cm:
            D[1::2]().validate(['1', '2'])
        self.assertEqual(
            str(cm.exception),
            'value has 2 elements, but multiplicity must be an integer multiple of 2 above 1')

    def test_each_element_is_validated(self):
        with self.assertRaises(ValueError):
            Tool.Input.Directory[:]().validate(['a', 'b/'])
        with self.assertRaises(ValueError):
            Tool.Input.Directory[:]().validate(['a/', 'b'])

    def test_element_must_not_be_none_even_if_dependency_role_not_required(self):
        with self.assertRaises(ValueError) as cm:
            Tool.Input.Directory[:](is_required=False).validate([None])
        self.assertEqual(str(cm.exception), 'required dependency must not be None')


# noinspection PyPep8Naming
class MultiplicityTest(unittest.TestCase):

    def test_no_multiplicity(self):
        M = Tool.Dependency
        self.assertIsNone(M.multiplicity)

        self.assertTrue(M.is_multiplicity_valid(None))
        self.assertFalse(M.is_multiplicity_valid(0))
        self.assertFalse(M.is_multiplicity_valid(1))

    def test_int_multiplicity(self):
        M = Tool.Dependency[0]
        self.assertFalse(M.is_multiplicity_valid(-1))
        self.assertTrue(M.is_multiplicity_valid(0))
        self.assertFalse(M.is_multiplicity_valid(1))

        M = Tool.Dependency[100]
        self.assertFalse(M.is_multiplicity_valid(99))
        self.assertTrue(M.is_multiplicity_valid(100))
        self.assertFalse(M.is_multiplicity_valid(101))

    def test_slice_multiplicity(self):
        M = Tool.Dependency[2:]
        self.assertFalse(M.is_multiplicity_valid(1))
        self.assertTrue(M.is_multiplicity_valid(2))
        self.assertTrue(M.is_multiplicity_valid(3))

        M = Tool.Dependency[:2]
        self.assertTrue(M.is_multiplicity_valid(0))
        self.assertTrue(M.is_multiplicity_valid(1))
        self.assertFalse(M.is_multiplicity_valid(2))

        M = Tool.Dependency[:]
        self.assertTrue(M.is_multiplicity_valid(0))
        self.assertTrue(M.is_multiplicity_valid(1))
        self.assertTrue(M.is_multiplicity_valid(100))

        M = Tool.Dependency[1::5]
        self.assertFalse(M.is_multiplicity_valid(0))
        self.assertTrue(M.is_multiplicity_valid(1))
        self.assertFalse(M.is_multiplicity_valid(2))
        self.assertFalse(M.is_multiplicity_valid(5))
        self.assertTrue(M.is_multiplicity_valid(6))
        self.assertFalse(M.is_multiplicity_valid(7))

    def test_nonint_multiplicity(self):
        with self.assertRaises(TypeError) as cm:
            Tool.Dependency[:].is_multiplicity_valid('')
        self.assertEqual(str(cm.exception), 'multiplicity must be None or integer')

    def test_is_normalized(self):
        self.assertEqual(
            Tool.Input.Directory[:].multiplicity,
            Tool.Input.Directory[0::].multiplicity)

        self.assertEqual(
            Tool.Input.Directory[2].multiplicity,
            Tool.Input.Directory[2:3].multiplicity)

        self.assertEqual(
            Tool.Input.Directory[100:0].multiplicity,
            Tool.Input.Directory[0].multiplicity)

        self.assertEqual(
            Tool.Input.Directory[10:15:10].multiplicity,
            Tool.Input.Directory[10].multiplicity)

        self.assertEqual(
            Tool.Input.Directory[10:55:10].multiplicity,
            Tool.Input.Directory[10:51:10].multiplicity)

    def test_cannot_be_nested(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyStatementEffect
            Tool.Dependency[:][:]
        self.assertEqual(str(cm.exception), 'dependency role with multiplicity is not subscriptable')
