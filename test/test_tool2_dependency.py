import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex.tool2.dependency
import dlb.ex.mult
import re
import unittest
import tools_for_test


class TestDependency(unittest.TestCase):

    def test_is_multiplicity_holder(self):
        d = dlb.ex.tool2.dependency.Dependency()
        self.assertIsInstance(d, dlb.ex.mult.MultiplicityHolder)

    def test_validate_fail_with_meaningful_message(self):
        msg = (
            "<class 'dlb.ex.tool2.dependency.Dependency'> is abstract\n"
            "  | use one of its documented subclasses instead"
        )

        d = dlb.ex.tool2.dependency.Dependency()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate('', None)
        self.assertEqual(msg, str(cm.exception))

        d = dlb.ex.tool2.dependency.Dependency[:]()
        with self.assertRaises(NotImplementedError) as cm:
            d.validate([1], None)
        self.assertEqual(msg, str(cm.exception))


class TestCommonOfNonAbstractDependency(unittest.TestCase):

    # stands for any non-abstract subclass of Dependency:
    D = dlb.ex.tool2.dependency.RegularFileInput

    def test_validate_with_multiplicity_mismatch_fails_with_meaningful_message(self):
        d = TestCommonOfNonAbstractDependency.D[1:]()
        with self.assertRaises(ValueError) as cm:
            d.validate([], None)
        msg = 'value has 0 members, which is not accepted according to the specified multiplicity [1:]'
        self.assertEqual(msg, str(cm.exception))

    def test_duplicate_free_cannot_contain_duplicates(self):
        paths = ['1', '2', '1']
        TestCommonOfNonAbstractDependency.D[:](unique=False).validate(paths, None)
        with self.assertRaises(ValueError) as cm:
            TestCommonOfNonAbstractDependency.D[:](unique=True).validate(paths, None)
        msg = "sequence of dependencies must be duplicate-free, but contains Path('1') more than once"
        self.assertEqual(str(cm.exception), msg)

    def test_value_must_be_iterable(self):
        with self.assertRaises(TypeError) as cm:
            TestCommonOfNonAbstractDependency.D[:]().validate(1, None)
        msg = "'int' object is not iterable"
        self.assertEqual(str(cm.exception), msg)

    def test_validate_with_str_of_bytes_fails_with_meaningful_message(self):
        msg = "since dependency has a multiplicity, value must be iterable (other than 'str' or 'bytes')"
        d = TestCommonOfNonAbstractDependency.D[:]()

        with self.assertRaises(TypeError) as cm:
            d.validate('', None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            d.validate(b'', None)
        self.assertEqual(msg, str(cm.exception))

    def test_each_member_is_validated(self):
        with self.assertRaises(ValueError):
            TestCommonOfNonAbstractDependency.D[:]().validate(['a', 'b/'], None)
        with self.assertRaises(ValueError):
            TestCommonOfNonAbstractDependency.D[:]().validate(['a/', 'b'], None)

    def test_member_count_must_match_multiplicity(self):
        with self.assertRaises(ValueError) as cm:
            TestCommonOfNonAbstractDependency.D[2:]().validate([], None)
        msg = "value has 0 members, which is not accepted according to the specified multiplicity [2:]"
        self.assertEqual(str(cm.exception), msg)


class TestAbstractDependencyClasses(unittest.TestCase):

    def test_fails_with_meaningful_message(self):
        msg_tmpl = (
            "<class {!r}> is abstract\n"
            "  | use one of its documented subclasses instead"
        )

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.tool2.dependency.Dependency().validate(0, None)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.tool2.dependency.Dependency'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.tool2.dependency.Input().validate(0, None)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.tool2.dependency.Input'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.tool2.dependency.Intermediate().validate(0, None)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.tool2.dependency.Intermediate'))

        with self.assertRaises(NotImplementedError) as cm:
            dlb.ex.tool2.dependency.Output().validate(0, None)
        self.assertEqual(str(cm.exception), msg_tmpl.format('dlb.ex.tool2.dependency.Output'))


class TestSingleInputType(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_none(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.tool2.dependency.RegularFileInput().validate(None, None)
        self.assertEqual(str(cm.exception), "'value' must not be None")

    def test_fails_for_invalid_path_conversion(self):
        with self.assertRaises(ValueError):
            dlb.ex.tool2.dependency.RegularFileInput(cls=dlb.fs.NoSpacePath).validate('a /b', None)

    def test_regular_file_returns_path(self):
        v = dlb.ex.tool2.dependency.RegularFileInput(cls=dlb.fs.NoSpacePath).validate('a/b', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_nonregular_file_returns_path(self):
        v = dlb.ex.tool2.dependency.NonRegularFileInput(cls=dlb.fs.NoSpacePath).validate('a/b', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_directory_returns_path(self):
        v = dlb.ex.tool2.dependency.DirectoryInput(cls=dlb.fs.NoSpacePath).validate('a/b/', None)
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

            v = dlb.ex.tool2.dependency.EnvVarInput(
                restriction=r'[0-9]+[a-z]+', example='42s').validate('UV', c)
            self.assertEqual(v, '123mm')

            v = dlb.ex.tool2.dependency.EnvVarInput(
                restriction=r'(?P<num>[0-9]+)(?P<unit>[a-z]+)', example='42s').validate('UV', c)
            self.assertEqual(v, {'num': '123', 'unit': 'mm'})


class TestInputProperty(unittest.TestCase):

    def test_filesystem_input_dependency_has_cls_and_(self):
        d = dlb.ex.tool2.dependency.RegularFileInput()
        self.assertIs(d.cls, dlb.fs.Path)
        self.assertTrue(d.ignore_permission)

        d = dlb.ex.tool2.dependency.RegularFileInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)
        d = dlb.ex.tool2.dependency.RegularFileInput(ignore_permission=False)
        self.assertFalse(d.ignore_permission)

        d = dlb.ex.tool2.dependency.NonRegularFileInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)
        d = dlb.ex.tool2.dependency.RegularFileInput(ignore_permission=False)
        self.assertFalse(d.ignore_permission)

        d = dlb.ex.tool2.dependency.DirectoryInput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)
        d = dlb.ex.tool2.dependency.RegularFileInput(ignore_permission=False)
        self.assertFalse(d.ignore_permission)

    def test_filesystem_output_dependency_has_cls(self):

        d = dlb.ex.tool2.dependency.RegularFileOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.tool2.dependency.NonRegularFileOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

        d = dlb.ex.tool2.dependency.DirectoryOutput(cls=dlb.fs.NoSpacePath)
        self.assertIs(d.cls, dlb.fs.NoSpacePath)

    def test_envvar_intput_dependency_has_restriction_example(self):
        d = dlb.ex.tool2.dependency.EnvVarInput(restriction=r'.', example='!')
        self.assertEqual(re.compile(r'.'), d.restriction)
        self.assertEqual('!', d.example)


class TestFileInputValidation(unittest.TestCase):

    def test_fails_for_directory(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.tool2.dependency.RegularFileInput().validate('a/b/', None)
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")

        with self.assertRaises(ValueError) as cm:
            dlb.ex.tool2.dependency.NonRegularFileInput().validate('a/b/', None)
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")


class TestDirectoryInputValidation(unittest.TestCase):

    def test_fails_for_fil(self):

        with self.assertRaises(ValueError) as cm:
            dlb.ex.tool2.dependency.DirectoryInput().validate('a/b', None)
        self.assertEqual(str(cm.exception), "non-directory path not valid for directory dependency: Path('a/b')")


class TestEnvVarInputValidation(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_with_nonmatching_example(self):
        with self.assertRaises(ValueError) as cm:
            dlb.ex.tool2.dependency.EnvVarInput(restriction=r'[0-9]+', example='42s')
        self.assertEqual(str(cm.exception), "'example' is invalid with respect to 'restriction': '42s'")

    def test_fails_without_context(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.tool2.dependency.EnvVarInput(restriction=r'[0-9]+[a-z]+', example='42s').validate('UV', None)
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
                dlb.ex.tool2.dependency.EnvVarInput(restriction=r'[0-9]+[a-z]+', example='42s').validate('UV', c)
            msg = "value of environment variable 'UV' is invalid with respect to restriction: '123mm2'"
            self.assertEqual(str(cm.exception), msg)

    def test_fail_on_undefined(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c:
            with self.assertRaises(ValueError) as cm:
                dlb.ex.tool2.dependency.EnvVarInput(restriction=r'[0-9]+[a-z]+', example='42s').validate('UV', c)
            msg = (
                "not a defined environment variable in the context: 'UV'\n"
                "  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...]' = ..."
            )
            self.assertEqual(str(cm.exception), msg)


class TestSingleOutputType(unittest.TestCase):

    def test_fail_for_none(self):
        with self.assertRaises(TypeError) as cm:
            dlb.ex.tool2.dependency.RegularFileOutput().validate(None, None)
        self.assertEqual(str(cm.exception), "'value' must not be None")

    def test_regular_file_returns_path(self):
        v = dlb.ex.tool2.dependency.RegularFileOutput(cls=dlb.fs.NoSpacePath).validate('a/b', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_nonregular_file_returns_path(self):
        v = dlb.ex.tool2.dependency.NonRegularFileOutput(cls=dlb.fs.NoSpacePath).validate('a/b', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b'))

    def test_directory_returns_path(self):
        v = dlb.ex.tool2.dependency.DirectoryOutput(cls=dlb.fs.NoSpacePath).validate('a/b/', None)
        self.assertEqual(v, dlb.fs.NoSpacePath('a/b/'))
