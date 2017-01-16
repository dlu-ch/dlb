import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

from dlb.cmd.tool import Tool
import unittest


class InheritanceTest(unittest.TestCase):

    def test_hierarchy_matches_nesting(self):
        self.assertTrue(issubclass(Tool.Input, Tool.DependencyRole))
        self.assertTrue(issubclass(Tool.Input.RegularFile, Tool.Input))

        self.assertTrue(issubclass(Tool.Output, Tool.DependencyRole))
        self.assertTrue(issubclass(Tool.Output.RegularFile, Tool.Output))


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
        D = Tool.Input.Directory

        with self.assertRaises(TypeError):
            D[:]().validate(1)

        with self.assertRaises(TypeError) as cm:
            D[:]().validate('abc')
        self.assertEqual(
            str(cm.exception),
            'since dependency role has a multiplicity, value must be iterable (other than string)')

    def test_element_count_must_match_multiplicity(self):
        D = Tool.Input.Directory

        with self.assertRaises(ValueError) as cm:
            D[2:]().validate([])
        self.assertEqual(
            str(cm.exception),
            'value has 0 elements, but minimum multiplicity is 2')

        with self.assertRaises(ValueError) as cm:
            D[0:4:2]().validate(['1/', '2/', '3/'])
        self.assertEqual(
            str(cm.exception),
            'value has 3 elements, but maximum multiplicity is 2')

        with self.assertRaises(ValueError) as cm:
            D[1::2]().validate(['1/', '2/'])
        self.assertEqual(
            str(cm.exception),
            'value has 2 elements, but multiplicity must be an integer multiple of 2 above 1')

    def test_each_element_is_validated(self):
        D = Tool.Input.Directory

        with self.assertRaises(ValueError):
            D[:]().validate(['a', 'b/'])
        with self.assertRaises(ValueError):
            D[:]().validate(['a/', 'b'])

    def test_element_must_not_be_none_even_if_dependency_role_not_required(self):
        D = Tool.Input.Directory
        with self.assertRaises(ValueError) as cm:
            D[:](is_required=False).validate([None])
        self.assertEqual(str(cm.exception), 'required dependency must not be None')

    def test_duplicate_free_cannot_contain_duplicates(self):
        D = Tool.Input.Directory
        paths = ['1/', '2/', '1/']
        D[:](is_duplicate_free=False).validate(paths)
        with self.assertRaises(ValueError) as cm:
            D[:](is_duplicate_free=True).validate(paths)
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
