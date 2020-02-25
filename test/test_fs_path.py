# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import pathlib
import unittest


class ConstructionTest(unittest.TestCase):

    def test_from_absolute_as_string(self):
        p = dlb.fs.Path('/x//../yz/.////u')
        self.assertEqual(repr(p), "Path('/x/../yz/u')")
        self.assertTrue(p.is_absolute())

        # note: according to IEEE Std 1003.1-2008, §3.2, this is _not_ an absolute path:
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

    def test_backslash_is_normal_character(self):
        p = dlb.fs.Path('a\\b')
        self.assertEqual(repr(p), "Path('a\\\\b')")
        self.assertEqual(len(p.parts), 1)

    def test_from_empty_string(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('')
        self.assertEqual("invalid path: ''", str(cm.exception))

    def test_from_path(self):
        p = dlb.fs.Path('a/b/c')
        p2 = dlb.fs.Path(p)
        self.assertEqual(repr(p), "Path('a/b/c')")
        self.assertEqual(repr(p2), "Path('a/b/c')")

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

    def test_from_tuple(self):
        self.assertEqual(dlb.fs.Path('a\\b/c'), dlb.fs.Path(('', 'a\\b', 'c')))
        self.assertEqual(dlb.fs.Path('/a/b'), dlb.fs.Path(('/', 'a', '.', 'b', '', '', '.')))
        self.assertEqual(dlb.fs.Path('//a/b'), dlb.fs.Path(('//', 'a', 'b')))
        self.assertEqual(dlb.fs.Path('///a/b'), dlb.fs.Path(('/', 'a', 'b')))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(())
        self.assertEqual("if 'path' is a tuple, its first element must be one of '', '/', '//'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(('x',))
        self.assertEqual("if 'path' is a tuple, its first element must be one of '', '/', '//'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(('///',))
        self.assertEqual("if 'path' is a tuple, its first element must be one of '', '/', '//'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(('', 'a/b'))
        self.assertEqual("if 'path' is a tuple, none except its first element must contain '/'", str(cm.exception))

    def test_from_none(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(None)
        self.assertEqual("invalid path: None", str(cm.exception))

    def test_from_int(self):
        with self.assertRaises(TypeError) as cm:
            dlb.fs.Path(1)
        msg = "'path' must be a str, dlb.fs.Path or pathlib.PurePath object or an sequence"
        self.assertEqual(msg, str(cm.exception))


class StringRepresentationTest(unittest.TestCase):

    def test_repr(self):
        p = dlb.fs.Path('x//../yz/.////u')
        self.assertEqual(repr(p), "Path('x/../yz/u')")

    def test_str(self):
        p = dlb.fs.Path('x//../yz/.////u')
        with self.assertRaises(AttributeError) as cm:
            str(p)
        self.assertEqual("use 'repr()' or 'native' instead", str(cm.exception))


class ConversionFromAnToPurePathTest(unittest.TestCase):

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

    def test_incomplete_windowspath_is_not_permitted(self):
        self.assertEqual(pathlib.PureWindowsPath(r'C:\\'), dlb.fs.Path('/c:').pure_windows)  # add root

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('/c:a').pure_windows
        self.assertEqual("neither absolute nor relative: drive is missing", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('//name').pure_windows
        self.assertEqual("neither absolute nor relative: drive is missing", str(cm.exception))

    def test_reserved_is_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('com2').pure_windows
        self.assertEqual("path is reserved", str(cm.exception))


class IsDirConstructionTest(unittest.TestCase):

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


class OrderingAndComparisonTest(unittest.TestCase):

    def test_comparison_is_casesensitive_on_all_platforms(self):
        a = dlb.fs.Path('/c:/')
        b = dlb.fs.Path('/C:/')

        self.assertTrue(a == a)
        self.assertTrue(b == b)
        self.assertTrue(a != b)

    def test_nondir_and_dir_are_different(self):
        a = dlb.fs.Path('/x/y')
        b = dlb.fs.Path('/x/y/')

        self.assertTrue(a == a)
        self.assertTrue(b == b)
        self.assertTrue(a != b)

    def test_order_of_absolute(self):
        self.assertTrue(dlb.fs.Path('/a/y') < dlb.fs.Path('/a/y/'))
        self.assertTrue(dlb.fs.Path('/x/b/') < dlb.fs.Path('/x/b/c'))
        self.assertTrue(dlb.fs.Path('/x/b/c') < dlb.fs.Path('/x/b/c/'))

    def test_order_of_relative(self):
        self.assertTrue(dlb.fs.Path('a/y') < dlb.fs.Path('a/y/'))
        self.assertTrue(dlb.fs.Path('x/b/') < dlb.fs.Path('x/b/c'))
        self.assertTrue(dlb.fs.Path('x/b/c') < dlb.fs.Path('x/b/c/'))

    def test_order_of_absolute_and_relative(self):
        self.assertTrue(dlb.fs.Path('a/y') < dlb.fs.Path('/a/y'))
        self.assertTrue(dlb.fs.Path('$/y') < dlb.fs.Path('/$/y'))

    def test_can_be_set_element(self):
        s = {dlb.fs.Path('/x/y/'), dlb.fs.Path('/x/y'), dlb.fs.Path('/a/..')}
        self.assertEqual(len(s), 3)


class TransformationTest(unittest.TestCase):

    def test_appending_relative_to_dir_is_possible(self):
        p = dlb.fs.Path('..') / dlb.fs.Path('a/b/c/d')
        self.assertEqual(p, dlb.fs.Path('../a/b/c/d'))

        p = dlb.fs.Path('..') / 'a/b/c/d/'
        self.assertEqual(p, dlb.fs.Path('../a/b/c/d/'))

        p = '/u/v/../' / dlb.fs.Path('a/b/c/d')
        self.assertEqual(p, dlb.fs.Path('/u/v/../a/b/c/d'))

        p = '/u/v/' / dlb.fs.Path('.')
        self.assertEqual(p, dlb.fs.Path('/u/v/'))

    def test_appending_relative_to_nondir_is_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('../x') / dlb.fs.Path('a/b/c/d')
        self.assertEqual("cannot append to non-directory path: Path('../x')", str(cm.exception))

    def test_appending_absolute_to_dir_is_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('..') / dlb.fs.Path('/a/b/c/d')
        self.assertEqual("cannot append absolute path: Path('/a/b/c/d')", str(cm.exception))

    def test_relative_removes_prefix(self):
        p = dlb.fs.Path('../../a/b/c/../d/e/f/').relative_to('../../a/b/')
        self.assertEqual(p, dlb.fs.Path('c/../d/e/f/'))

        p = dlb.fs.Path('../../a/b/c/../d/e/f/').relative_to('.')
        self.assertEqual(p, dlb.fs.Path('../../a/b/c/../d/e/f/'))

        p = dlb.fs.Path('/u/v/w').relative_to('/u/v/')
        self.assertEqual(p, dlb.fs.Path('w'))

        p = dlb.fs.Path('/u/v/w').relative_to('/')
        self.assertEqual(p, dlb.fs.Path('u/v/w'))

    def test_relative_fails_for_nondirectory(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a').relative_to(dlb.fs.Path('b'))
        self.assertEqual("since Path('b') is not a directory, a path cannot be relative to it", str(cm.exception))

    def test_relative_fails_for_nonprefix(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a').relative_to(dlb.fs.Path('b/'))
        self.assertEqual("'a' does not start with 'b/'", str(cm.exception))

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
            p[-1:0:-1]
        self.assertEqual("slice step must be positive", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            p[:-4]
        self.assertEqual("slice of absolute path starting at 0 must not be empty", str(cm.exception))
        self.assertEqual(dlb.fs.Path('.'), p[1:-4])

        p = dlb.fs.Path('//u/v/w')
        self.assertEqual(p[:], p)
        self.assertEqual(p[1:], dlb.fs.Path('u/v/w'))
        self.assertEqual(p[:-1], dlb.fs.Path('//u/v/'))
        self.assertEqual(p[:-2], dlb.fs.Path('//u/'))
        self.assertEqual(p[:-3], dlb.fs.Path('//'))

        with self.assertRaises(TypeError) as cm:
            p[0]
        self.assertEqual("slice of component indices expected (use 'parts' for single components)", str(cm.exception))


class DirectoryListingTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.tmp_dir_obj = tempfile.TemporaryDirectory()
        self.tmp_dir = dlb.fs.Path(dlb.fs.Path.Native(self.tmp_dir_obj.name), is_dir=True)
        (self.tmp_dir / 'a1').native.touch()
        (self.tmp_dir / 'a2/').native.mkdir()
        (self.tmp_dir / 'b1').native.touch()
        (self.tmp_dir / 'b3').native.touch()
        (self.tmp_dir / 'b4').native.touch()
        (self.tmp_dir / 'b2/').native.mkdir()
        (self.tmp_dir / 'b2/c3/').native.mkdir()
        (self.tmp_dir / 'b2/c3/d1').native.touch()
        (self.tmp_dir / 'b2/c3/d2').native.touch()

    def tearDown(self):
        self.tmp_dir_obj.cleanup()

    def test_error_on_nondir(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('./x').list()
        self.assertEqual("cannot list non-directory path: 'x'", str(cm.exception))

    def test_listed_paths_are_complete_and_ordered(self):

        expected_rel_paths = [dlb.fs.Path(s) for s in [
            'a1',
            'a2/',
            'b1',
            'b3',
            'b4',
            'b2/',
            'b2/c3/',
            'b2/c3/d1',
            'b2/c3/d2'
        ]]
        expected_rel_paths.sort()

        paths = self.tmp_dir.list(recurse_name_filter='')
        rel_paths = self.tmp_dir.list_r(recurse_name_filter='')
        self.assertEqual(set(rel_paths), set(expected_rel_paths))
        self.assertEqual({p.relative_to(self.tmp_dir) for p in paths}, set(expected_rel_paths))

        self.assertEqual(rel_paths, expected_rel_paths)
        self.assertEqual([p.relative_to(self.tmp_dir) for p in paths], expected_rel_paths)

    def test_namefilter_can_be_none(self):
        rel_paths = self.tmp_dir.list_r(name_filter=None)
        self.assertEqual(rel_paths, [])

    def test_namefilter_can_be_empty_string(self):
        expected_rel_paths = [dlb.fs.Path(s) for s in [
            'a1',
            'a2/',
            'b1',
            'b3',
            'b4',
            'b2/',
        ]]
        expected_rel_paths.sort()

        rel_paths = self.tmp_dir.list_r(name_filter='')
        self.assertEqual(rel_paths, expected_rel_paths)

    def test_namefilter_can_be_regexp(self):
        import re

        expected_rel_paths = [dlb.fs.Path(s) for s in [
            'b1',
            'b3',
            'b4',
            'b2/',
        ]]
        expected_rel_paths.sort()

        regexp_str = 'b[0-9]+'
        rel_paths = self.tmp_dir.list_r(name_filter=regexp_str)
        self.assertEqual(rel_paths, expected_rel_paths)

        regexp_str = 'b[0-9]+'
        rel_paths = self.tmp_dir.list_r(name_filter=re.compile(regexp_str))
        self.assertEqual(rel_paths, expected_rel_paths)

    def test_namefilter_can_be_callable(self):
        expected_rel_paths = [dlb.fs.Path(s) for s in [
            'a2/',
            'b2/',
            'b2/c3/d2'
        ]]
        expected_rel_paths.sort()

        def f(n):
            return n.endswith('2')

        rel_paths = self.tmp_dir.list_r(name_filter=f, recurse_name_filter='')
        self.assertEqual(rel_paths, expected_rel_paths)

    def test_error_on_invalid_namefilter(self):
        with self.assertRaises(TypeError) as cm:
            self.tmp_dir.list_r(name_filter=1, recurse_name_filter='')
        self.assertEqual("invalid name filter: 1", str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            self.tmp_dir.list_r(name_filter=None, recurse_name_filter=2)
        self.assertEqual("invalid name filter: 2", str(cm.exception))

    def test_listed_paths_are_of_requested_class(self):
        class MyPath(dlb.fs.Path):
            pass

        rel_paths = self.tmp_dir.list_r(name_filter='', cls=MyPath)

        self.assertTrue(len(rel_paths) > 0)
        self.assertEqual({isinstance(p, MyPath) for p in rel_paths}, {True})

    def test_error_on_invalid_class(self):
        with self.assertRaises(TypeError) as cm:
            self.tmp_dir.list_r(cls=int)
        self.assertEqual("'cls' must be None or a subclass of 'dlb.fs.Path'", str(cm.exception))


class NativeTest(unittest.TestCase):

    def test_str_prefixes_relative_with_dot(self):
        s = str(dlb.fs.Path('x').native)
        self.assertEqual(s.replace('\\', '/'), './x')
        self.assertEqual(str(dlb.fs.Path('.').native), '.')
        self.assertEqual(str(dlb.fs.Path('..').native), '..')

    def test_repr(self):
        p = dlb.fs.Path('x').native
        self.assertEqual("Path.Native('./x')", repr(p))

    def test_is_pathlike(self):
        import os
        p = dlb.fs.Path.Native('x')
        self.assertTrue(isinstance(p, os.PathLike))

    def test_restrictions_are_checked_exactly_once_when_converted_to_native(self):

        class CheckCountingPath(dlb.fs.Path):
            n = 0

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def check_restriction_to_base(self):
                self.__class__.n += 1

        p = CheckCountingPath('x')
        self.assertEqual(1, CheckCountingPath.n)

        p.native
        self.assertEqual(1, CheckCountingPath.n)

        CheckCountingPath.Native('x')
        self.assertEqual(2, CheckCountingPath.n)

    def test_isinstance_checks_restrictions(self):

        self.assertIsInstance(dlb.fs.Path('a').native, dlb.fs.Path.Native)
        self.assertIsInstance(dlb.fs.NoSpacePath('a').native, dlb.fs.Path.Native)
        self.assertNotIsInstance(dlb.fs.Path('a ').native, dlb.fs.NoSpacePath)
        self.assertNotIsInstance(dlb.fs.Path('a ').native, dlb.fs.NoSpacePath.Native)
        self.assertNotIsInstance(dlb.fs.Path('a '), dlb.fs.NoSpacePath.Native)

    def test_issubclass(self):

        self.assertFalse(issubclass(dlb.fs.Path.Native, dlb.fs.Path))
        self.assertTrue(issubclass(dlb.fs.NoSpacePath.Native, dlb.fs.Path.Native))
        self.assertFalse(issubclass(dlb.fs.NoSpacePath.Native, dlb.fs.PortableWindowsPath.Native))


@unittest.skipIf(pathlib.Path is not pathlib.WindowsPath, 'Windows only')
class NativeWindowsTest(unittest.TestCase):

    def test_constructor_fails_for_invalid_path(self):
        with self.assertRaises(ValueError):
            dlb.fs.Path.Native('a:b')

        with self.assertRaises(ValueError):
            dlb.fs.Path.Native(pathlib.Path('a') / "*" / ":")


class RelativeRestrictionsTest(unittest.TestCase):

    def test_relative_permitted(self):
        dlb.fs.RelativePath('a/b/c')

    def test_absolute_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.RelativePath('/a/b/c')
        self.assertEqual("invalid path for 'RelativePath': '/a/b/c' (must be relative)", str(cm.exception))


class AbsoluteRestrictionsTest(unittest.TestCase):

    def test_absolute_permitted(self):
        dlb.fs.AbsolutePath('/a/b/c')

    def test_absolute_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.AbsolutePath('a/b/c')
        self.assertEqual("invalid path for 'AbsolutePath': 'a/b/c' (must be absolute)", str(cm.exception))


class NormalizedRestrictionsTest(unittest.TestCase):

    def test_relative_permitted(self):
        dlb.fs.NormalizedPath('/a/b/c')

    def test_absolute_permitted(self):
        dlb.fs.NormalizedPath('/a/b/c')

    def test_absolute_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.NormalizedPath('a/../b')
        self.assertEqual("invalid path for 'NormalizedPath': 'a/../b' (must be normalized)", str(cm.exception))


class NoSpaceRestrictionsTest(unittest.TestCase):

    def test_space_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.NoSpacePath('a b')
        self.assertEqual("invalid path for 'NoSpacePath': 'a b' (must not contain space)", str(cm.exception))


class PosixRestrictionsTest(unittest.TestCase):

    def test_null_not_permitted(self):
        # IEEE Std 1003.1-2008, §3.170
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PosixPath('a\x00b')
        self.assertEqual("invalid path for 'PosixPath': 'a\\x00b' (must not contain NUL)", str(cm.exception))


class PortablePosixRestrictionsTest(unittest.TestCase):

    def test_slashslash_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('//unc/root/d')
        msg = (
            "invalid path for 'PortablePosixPath': '//unc/root/d' "
            "(non-standardized component starting with '//' not allowed)"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_leadingdash_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('/a/-b')
        msg = "invalid path for 'PortablePosixPath': '/a/-b' (component must not start with '-')"
        self.assertEqual(msg, str(cm.exception))

    def test_backslash_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('a\\b')
        msg = r"invalid path for 'PortablePosixPath': 'a\\b' (must not contain these characters: '\\')"
        self.assertEqual(msg, str(cm.exception))

    def test_too_long_component_not_permitted(self):
        dlb.fs.PortablePosixPath('a' * dlb.fs.PortablePosixPath.MAX_COMPONENT_LENGTH)
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('a' * (dlb.fs.PortablePosixPath.MAX_COMPONENT_LENGTH + 1))
        msg = (
            "invalid path for 'PortablePosixPath': 'aaaaaaaaaaaaaaa' "
            "(component must not contain more than 14 characters)"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_too_long_not_permitted(self):
        dlb.fs.PortablePosixPath('a/' * (dlb.fs.PortablePosixPath.MAX_PATH_LENGTH // 2) + 'b')

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('a/' * (dlb.fs.PortablePosixPath.MAX_PATH_LENGTH // 2) + 'bc')
        self.assertTrue(str(cm.exception).endswith(" (must not contain more than 255 characters)"))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('a/' * (dlb.fs.PortablePosixPath.MAX_PATH_LENGTH // 2) + 'b/')
        self.assertTrue(str(cm.exception).endswith(" (must not contain more than 255 characters)"))


class WindowsRestrictionsTest(unittest.TestCase):

    def test_backslash_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a\\b')
        self.assertEqual("invalid path for 'WindowsPath': 'a\\\\b' (must not contain reserved characters: '\\\\')",
                         str(cm.exception))

    def test_null_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a\x00b')
        self.assertEqual(
            "invalid path for 'WindowsPath': 'a\\x00b' "
            "(must not contain characters with codepoint lower than U+0020: U+0000)",
            str(cm.exception))

    def test_control_character_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a\nb')
        self.assertEqual(
            "invalid path for 'WindowsPath': 'a\\nb' "
            "(must not contain characters with codepoint lower than U+0020: U+000A)",
            str(cm.exception))

    def test_non_bmp_character_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a\U00010000b')
        self.assertEqual(
            "invalid path for 'WindowsPath': 'a\U00010000b' "
            "(must not contain characters with codepoint higher than U+FFFF: U+10000)",
            str(cm.exception))

    def test_colon_not_permitted_except_in_drive(self):
        dlb.fs.WindowsPath('/a:/b/c')

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a/b:/c')
        self.assertEqual("invalid path for 'WindowsPath': 'a/b:/c' (must not contain reserved characters: ':')",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a:/b/c')
        self.assertEqual("invalid path for 'WindowsPath': 'a:/b/c' (must not contain reserved characters: ':')",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('//a:/b/c')
        self.assertEqual("invalid path for 'WindowsPath': '//a:/b/c' (must not contain reserved characters: ':')",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('/:a/b/c')
        self.assertEqual("invalid path for 'WindowsPath': '/:a/b/c' (neither absolute nor relative: drive is missing)",
                         str(cm.exception))

    def test_start_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('/*:')
        self.assertEqual("invalid path for 'WindowsPath': '/*:' (must not contain reserved characters: '*')",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('//u*/r/d')
        self.assertEqual("invalid path for 'WindowsPath': '//u*/r/d' (must not contain reserved characters: '*')",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('r/*d')
        self.assertEqual("invalid path for 'WindowsPath': 'r/*d' (must not contain reserved characters: '*')",
                         str(cm.exception))

    def test_nonrelative_without_root_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('/')
        self.assertEqual("invalid path for 'WindowsPath': '/' (neither absolute nor relative: root is missing)",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('/a:b')
        self.assertEqual("invalid path for 'WindowsPath': '/a:b' (neither absolute nor relative: drive is missing)",
                         str(cm.exception))

    def test_reserved_file_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a/coM9')
        self.assertEqual("invalid path for 'WindowsPath': 'a/coM9' (path is reserved)", str(cm.exception))
        dlb.fs.WindowsPath('a/coM10')

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a/coM9/')
        self.assertEqual("invalid path for 'WindowsPath': 'a/coM9/' (path is reserved)", str(cm.exception))

    def test_space_or_dot_at_end_of_component_permitted(self):
        dlb.fs.WindowsPath('a/b./c ')


class PortableWindowsRestrictionsTest(unittest.TestCase):

    def test_space_at_end_of_component_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('a/b /c')
        self.assertEqual("invalid path for 'PortableWindowsPath': 'a/b /c' (component must not end with ' ' or '.')",
                         str(cm.exception))

    def test_dot_at_end_of_component_not_permitted(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('a/b./c')
        self.assertEqual("invalid path for 'PortableWindowsPath': 'a/b./c' (component must not end with ' ' or '.')",
                         str(cm.exception))
        dlb.fs.PortablePath('a/../c')

    def test_too_long_component_not_permitted(self):
        dlb.fs.PortableWindowsPath('a' * dlb.fs.PortableWindowsPath.MAX_COMPONENT_LENGTH)

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('a' * (dlb.fs.PortableWindowsPath.MAX_COMPONENT_LENGTH + 1))

        self.assertTrue(str(cm.exception).endswith(" (component must not contain more than 255 characters)"))

    def test_too_long_not_permitted(self):
        dlb.fs.PortableWindowsPath('a/' * (dlb.fs.PortableWindowsPath.MAX_PATH_LENGTH // 2) + 'b')

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('a/' * (dlb.fs.PortableWindowsPath.MAX_PATH_LENGTH // 2) + 'bc')
        self.assertTrue(str(cm.exception).endswith(" (must not contain more than 259 characters)"))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('a/' * (dlb.fs.PortableWindowsPath.MAX_PATH_LENGTH // 2) + 'b/')
        self.assertTrue(str(cm.exception).endswith(" (must not contain more than 259 characters)"))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('/C:/' + 'a/' * (dlb.fs.PortableWindowsPath.MAX_PATH_LENGTH // 2) + 'b/')
        self.assertTrue(str(cm.exception).endswith(" (must not contain more than 259 characters)"))
