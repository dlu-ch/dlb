import dlb.fs
import pathlib
import unittest


class TestConstruction(unittest.TestCase):

    def test_from_absolute_as_string(self):
        p = dlb.fs.Path('/x//../yz/.////u')
        self.assertEqual(repr(p), "Path('/x/../yz/u')")
        self.assertTrue(p.is_absolute())

        p = dlb.fs.Path('//x/y/../u')
        self.assertEqual(repr(p), "Path('//x/y/../u')")
        self.assertTrue(p.is_absolute())

        p = dlb.fs.Path('///x/y/../u')
        self.assertEqual(repr(p), "Path('/x/y/../u')")
        self.assertTrue(p.is_absolute())

    def test_from_relative_as_string(self):
        p = dlb.fs.Path('./x')
        self.assertEqual(repr(p), "Path('x')")
        self.assertTrue(not p.is_absolute())

        p = dlb.fs.Path('../x/y/../../../u')
        self.assertEqual(repr(p), "Path('../x/y/../../../u')")
        self.assertTrue(not p.is_absolute())

        p = dlb.fs.Path('x//../yz/.////u')
        self.assertEqual(repr(p), "Path('x/../yz/u')")
        self.assertTrue(not p.is_absolute())

    def test_from_relative_as_string_forced_as_dir(self):
        p = dlb.fs.Path('./x', is_dir=True)
        self.assertEqual(repr(p), "Path('x/')")
        p = dlb.fs.Path('./x/', is_dir=True)
        self.assertEqual(repr(p), "Path('x/')")

        p = dlb.fs.Path('.', is_dir=True)
        self.assertEqual(repr(p), "Path('./')")

        p = dlb.fs.Path('a/..', is_dir=True)
        self.assertEqual(repr(p), "Path('a/../')")

    def test_from_relative_as_string_forced_as_nondir(self):
        p = dlb.fs.Path('./x/', is_dir=False)
        self.assertEqual(repr(p), "Path('x')")
        p = dlb.fs.Path('./x', is_dir=False)
        self.assertEqual(repr(p), "Path('x')")

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('.', is_dir=False)
        self.assertEqual("cannot be the path of a non-directory: '.'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a/..', is_dir=False)
        self.assertEqual("cannot be the path of a non-directory: 'a/..'", str(cm.exception))

    def test_from_empty_string(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('')
        self.assertEqual("invalid path: ''", str(cm.exception))

    def test_from_path(self):
        p = dlb.fs.Path('a/b/c')
        p2 = dlb.fs.Path(p)
        self.assertEqual(repr(p), "Path('a/b/c')")

    def test_from_pathlib(self):
        p = dlb.fs.Path(pathlib.PurePosixPath('/a/b/c'))
        self.assertEqual(repr(p), "Path('/a/b/c')")
        p = dlb.fs.Path(pathlib.PurePosixPath('//a/b/c'))
        self.assertEqual(repr(p), "Path('//a/b/c')")

        p = dlb.fs.Path(pathlib.PureWindowsPath('C:\\a\\b\\c'))
        self.assertEqual(repr(p), "Path('/C:/a/b/c')")
        p = dlb.fs.Path(pathlib.PureWindowsPath('a\\b\\c'))
        self.assertEqual(repr(p), "Path('a/b/c')")
        p = dlb.fs.Path(pathlib.PureWindowsPath('\\\\name\\r\\a\\b\\c'))
        self.assertEqual(repr(p), "Path('//name/r/a/b/c')")

    def test_from_pathlib_incomplete(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(pathlib.PureWindowsPath('C:'))
        self.assertEqual("neither absolute nor relative: root is missing", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(pathlib.PureWindowsPath('C:a\\b\\c'))
        self.assertEqual("neither absolute nor relative: root is missing", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(pathlib.PureWindowsPath('\\\\name'))
        self.assertEqual("neither absolute nor relative: drive is missing", str(cm.exception))

    def test_from_none(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(None)
        self.assertEqual("invalid path: None", str(cm.exception))

    def test_from_int(self):
        with self.assertRaises(TypeError) as cm:
            dlb.fs.Path(1)
        self.assertEqual("argument should be a path or str object, not <class 'int'>", str(cm.exception))


class TestStringRepresentation(unittest.TestCase):

    def test_repr(self):
        p = dlb.fs.Path('x//../yz/.////u')
        self.assertEqual(repr(p), "Path('x/../yz/u')")

    def test_str(self):
        p = dlb.fs.Path('x//../yz/.////u')
        with self.assertRaises(NotImplementedError) as cm:
            str(p)
        self.assertEqual("use 'repr()' or 'native' instead", str(cm.exception))


class TestConversionFromAnToPurePath(unittest.TestCase):

    def test_posix_roundtrip_is_lossless(self):
        pp = pathlib.PurePosixPath('/a/b/../c/')
        self.assertEqual(dlb.fs.Path(pp).pure_posix, pp)

        pp = pathlib.PurePosixPath('//a/b/c')
        self.assertEqual(dlb.fs.Path(pp).pure_posix, pp)

    def test_windows_roundtrip_is_lossless(self):
        pw = pathlib.PureWindowsPath('C:\\a\\b\\c')
        self.assertEqual(dlb.fs.Path(pw).pure_windows, pw)

        pw = pathlib.PureWindowsPath('C:\\')
        self.assertEqual(dlb.fs.Path(pw).pure_windows, pw)

        pw = pathlib.PureWindowsPath('a\\b\\c')
        self.assertEqual(dlb.fs.Path(pw).pure_windows, pw)

        pw = pathlib.PureWindowsPath('\\\\name\\r\\a\\b\\c')
        self.assertEqual(dlb.fs.Path(pw).pure_windows, pw)

        pw = pathlib.PureWindowsPath('\\\\name\\r')
        self.assertEqual(dlb.fs.Path(pw).pure_windows, pw)

    def test_incomplete_windowspath_are_inhibited(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('/c:').pure_windows
        self.assertEqual("neither absolute nor relative: root is missing", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('//name').pure_windows
        self.assertEqual("neither absolute nor relative: drive is missing", str(cm.exception))


class TestIsDirConstruction(unittest.TestCase):

    def test_isdir_is_preserved_from_string(self):
        p = dlb.fs.Path('x')
        self.assertTrue(not p.is_dir())
        self.assertEqual(repr(p), "Path('x')")

        p = dlb.fs.Path('x/')
        self.assertTrue(p.is_dir())
        self.assertEqual(repr(p), "Path('x/')")

        p = dlb.fs.Path('.')
        self.assertTrue(p.is_dir())
        self.assertEqual(repr(p), "Path('./')")

        p = dlb.fs.Path('..')
        self.assertTrue(p.is_dir())
        self.assertEqual(repr(p), "Path('../')")

    def test_isdir_is_preserved_from_path(self):
        p = dlb.fs.Path(dlb.fs.Path('x'))
        self.assertTrue(not p.is_dir())
        p = dlb.fs.Path(dlb.fs.Path('x/'))
        self.assertTrue(p.is_dir())


class TestOrderingAndComparison(unittest.TestCase):

    def test_comparison_is_casesensitive_on_all_platforms(self):
        a = dlb.fs.Path('/c:/')
        b = dlb.fs.Path('/C:/')

        self.assertTrue(a == a)
        self.assertTrue(b == b)
        self.assertTrue(a != b)

    def test_dir_is_smaller_than_nondir(self):
        a = dlb.fs.Path('/x/y/')
        b = dlb.fs.Path('/x/y')

        self.assertTrue(a == a)
        self.assertTrue(b == b)
        self.assertTrue(a != b)
        self.assertTrue(a < b)

    def test_prefix_is_smaller(self):
        self.assertTrue(dlb.fs.Path('/x/y/') < dlb.fs.Path('/x/y/z'))
        self.assertTrue(dlb.fs.Path('/x/y') < dlb.fs.Path('/x/y/z'))

    def test_can_be_set_element(self):
        s = set([dlb.fs.Path('/x/y/'), dlb.fs.Path('/x/y'), dlb.fs.Path('/a/..')])
        self.assertEqual(len(s), 3)


class TestTransformation(unittest.TestCase):

    def test_appending_relative_to_dir_is_possible(self):
        p = dlb.fs.Path('..') / dlb.fs.Path('a/b/c/d')
        self.assertEqual(p, dlb.fs.Path('../a/b/c/d'))

        p = dlb.fs.Path('..') / 'a/b/c/d/'
        self.assertEqual(p, dlb.fs.Path('../a/b/c/d/'))

        p = '/u/v/../' / dlb.fs.Path('a/b/c/d')
        self.assertEqual(p, dlb.fs.Path('/u/v/../a/b/c/d'))

    def test_appending_relative_to_nondir_is_inhibited(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('../x') / dlb.fs.Path('a/b/c/d')
        self.assertEqual("cannot join with non-directory path: Path('../x')", str(cm.exception))

    def test_appending_absolute_to_dir_is_inhibited(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('..') / dlb.fs.Path('/a/b/c/d')
        self.assertEqual("cannot join with absolute path: Path('/a/b/c/d')", str(cm.exception))

    def test_relative_removes_prefix(self):
        p = dlb.fs.Path('../../a/b/c/../d/e/f/').relative_to('../../a/b/')
        self.assertEqual(p, dlb.fs.Path('c/../d/e/f/'))

        p = dlb.fs.Path('../../a/b/c/../d/e/f/').relative_to('.')
        self.assertEqual(p, dlb.fs.Path('../../a/b/c/../d/e/f/'))

        p = dlb.fs.Path('/u/v/w').relative_to('/u/v/')
        self.assertEqual(p, dlb.fs.Path('w'))

        p = dlb.fs.Path('/u/v/w').relative_to('/')
        self.assertEqual(p, dlb.fs.Path('u/v/w'))

    def test_parts_of_relative_and_absolute_are_different(self):
        p = dlb.fs.Path('u/v/w')
        self.assertEqual(p.parts, ('u', 'v', 'w'))

        p = dlb.fs.Path('/u/v/w')
        self.assertEqual(p.parts, ('/', 'u', 'v', 'w'))

    def test_parts_of_directory_and_nondirectory_are_equal(self):
        p = dlb.fs.Path('/u/v/w')
        self.assertEqual(p.parts, ('/', 'u', 'v', 'w'))

        p = dlb.fs.Path('/u/v/w/')
        self.assertEqual(p.parts, ('/', 'u', 'v', 'w'))

    def test_slice(self):
        p = dlb.fs.Path('u/v/w/')
        self.assertEqual(p[:], p)
        self.assertEqual(p[1:], dlb.fs.Path('v/w/'))
        self.assertEqual(p[:-1], dlb.fs.Path('u/v/'))
        self.assertEqual(p[:-2], dlb.fs.Path('u/'))
        self.assertEqual(p[:-3], dlb.fs.Path('.'))

        p = dlb.fs.Path('/u/v/w')
        self.assertEqual(p[:], p)
        self.assertEqual(p[1:], dlb.fs.Path('u/v/w'))
        self.assertEqual(p[:-1], dlb.fs.Path('/u/v/'))
        self.assertEqual(p[:-2], dlb.fs.Path('/u/'))
        self.assertEqual(p[:-3], dlb.fs.Path('/'))

        with self.assertRaises(ValueError) as cm:
            p[:-4]
        self.assertEqual("slice of absolute path must not be empty", str(cm.exception))

        p = dlb.fs.Path('//u/v/w')
        self.assertEqual(p[:], p)
        self.assertEqual(p[1:], dlb.fs.Path('u/v/w'))
        self.assertEqual(p[:-1], dlb.fs.Path('//u/v/'))
        self.assertEqual(p[:-2], dlb.fs.Path('//u/'))
        self.assertEqual(p[:-3], dlb.fs.Path('//'))
        with self.assertRaises(ValueError) as cm:
            p[:-4]
        self.assertEqual("slice of absolute path must not be empty", str(cm.exception))
