# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import sys
import os.path
import pathlib
import copy
import unittest


class PathFromStrTest(unittest.TestCase):

    def test_absolute(self):
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

    def test_relative(self):
        p = dlb.fs.Path('./x')
        self.assertEqual(repr(p), "Path('x')")
        self.assertTrue(not p.is_absolute())

        p = dlb.fs.Path('../x/y/../../../u')
        self.assertEqual(repr(p), "Path('../x/y/../../../u')")
        self.assertTrue(not p.is_absolute())

        p = dlb.fs.Path('x//../yz/.////u')
        self.assertEqual(repr(p), "Path('x/../yz/u')")
        self.assertTrue(not p.is_absolute())

    def test_relative_as_dir(self):
        p = dlb.fs.Path('./x', is_dir=True)
        self.assertEqual(repr(p), "Path('x/')")
        p = dlb.fs.Path('./x/', is_dir=True)
        self.assertEqual(repr(p), "Path('x/')")

        p = dlb.fs.Path('.', is_dir=True)
        self.assertEqual(repr(p), "Path('./')")

        p = dlb.fs.Path('a/..', is_dir=True)
        self.assertEqual(repr(p), "Path('a/../')")

    def test_relative_as_nondir(self):
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

    def test_fails_for_empty(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('')
        self.assertEqual("invalid path: ''", str(cm.exception))


class PathFromPathTest(unittest.TestCase):

    def test_from_path(self):
        p = dlb.fs.Path('a/b/c')
        p2 = dlb.fs.Path(p)
        self.assertEqual(repr(p), "Path('a/b/c')")
        self.assertEqual(repr(p2), "Path('a/b/c')")


class PathFromPathlibTest(unittest.TestCase):

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

    def test_fails_for_incomplete(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(pathlib.PureWindowsPath('C:'))
        self.assertEqual("neither absolute nor relative: root is missing", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(pathlib.PureWindowsPath('C:a\\b\\c'))
        self.assertEqual("neither absolute nor relative: root is missing", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(pathlib.PureWindowsPath('\\\\name'))
        self.assertEqual("neither absolute nor relative: drive is missing", str(cm.exception))


class PathFromSequenceTest(unittest.TestCase):

    def test_from_path_component_sequence(self):
        self.assertEqual(dlb.fs.Path('.'), dlb.fs.Path(()))
        self.assertEqual(dlb.fs.Path('.'), dlb.fs.Path(('',)))
        self.assertEqual(dlb.fs.Path('a\\b/c'), dlb.fs.Path(('a\\b', 'c')))
        self.assertEqual(dlb.fs.Path('a\\b/c'), dlb.fs.Path(('', 'a\\b', 'c')))
        self.assertEqual(dlb.fs.Path('/a/b'), dlb.fs.Path(('/', 'a', '.', 'b', '', '', '.')))
        self.assertEqual(dlb.fs.Path('//a/b'), dlb.fs.Path(('//', 'a', 'b')))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(('///',))
        msg = "if 'path' is a path component sequence, its first element must be one of '', '/', '//'"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(('', 'a/b'))
        msg = "if 'path' is a path component sequence, none except its first element must contain '/'"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path(('', '/a'))
        msg = "if 'path' is a path component sequence, none except its first element must contain '/'"
        self.assertEqual(msg, str(cm.exception))


class PathFromOtherTest(unittest.TestCase):

    def test_fails_for_none(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.Path(None)
        msg = (
            "'path' must be a str, dlb.fs.Path, dlb.fs.Path.Native, pathlib.PurePath, or a path component sequence, "
            "not <class 'NoneType'>"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_int(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.Path(1)
        msg = (
            "'path' must be a str, dlb.fs.Path, dlb.fs.Path.Native, pathlib.PurePath, or a path component sequence, "
            "not <class 'int'>"
        )
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


class ConversionFromAndToPurePathTest(unittest.TestCase):

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

    def test_fails_for_unsupported_purepath(self):
        class PureCustomPath(pathlib.PurePosixPath):
            pass

        pp = PureCustomPath('/a/b/../c/')
        pp.__class__.__bases__ = (pathlib.PurePath,)

        self.assertIsInstance(pp, pathlib.PurePath)
        self.assertNotIsInstance(pp, pathlib.PurePosixPath)

        with self.assertRaises(TypeError) as cm:
            dlb.fs.Path(pp)
        self.assertEqual("unknown subclass of 'pathlib.PurePath'", str(cm.exception))

    def test_fails_for_incomplete_windowspath(self):
        self.assertEqual(pathlib.PureWindowsPath(r'C:\\'), dlb.fs.Path('/c:').pure_windows)  # add root

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('/c:a').pure_windows
        self.assertEqual("neither absolute nor relative: drive is missing", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('//name').pure_windows
        self.assertEqual("neither absolute nor relative: drive is missing", str(cm.exception))

    def test_fails_for_reserved(self):
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


class AppendTest(unittest.TestCase):

    def test_relative_to_dir_is_possible(self):
        p = dlb.fs.Path('..') / dlb.fs.Path('a/b/c/d')
        self.assertEqual(p, dlb.fs.Path('../a/b/c/d'))

        p = dlb.fs.Path('..') / 'a/b/c/d/'
        self.assertEqual(p, dlb.fs.Path('../a/b/c/d/'))

    def test_fails_if_left_side_is_no_path(self):
        with self.assertRaises(TypeError):
            '/u/v/' / dlb.fs.Path('.')
        # dlb.fs.Path has no __rtruediv__ on purpuse.
        # reason: fewer surprises if type of right side is a subclass of type of left side

    def test_fails_for_nondir(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('../x') / dlb.fs.Path('a/b/c/d')
        self.assertEqual("cannot append to non-directory path: Path('../x')", str(cm.exception))

    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('..') / dlb.fs.Path('/a/b/c/d')
        self.assertEqual("cannot append absolute path: Path('/a/b/c/d')", str(cm.exception))

    def test_affects_native(self):
        p = dlb.fs.Path('a/b/c/')
        pn = str(p.native)
        p2 = p / dlb.fs.Path('x/y')
        pn2 = str(p2.native)
        self.assertNotEqual(pn2, pn)


class WithAppendedSuffixTest(unittest.TestCase):

    def test_typical_is_correct(self):
        self.assertEqual(dlb.fs.Path('a/b.o'), dlb.fs.Path('a/b').with_appended_suffix('.o'))
        self.assertEqual(dlb.fs.Path('/a/b.o'), dlb.fs.Path('/a/b').with_appended_suffix('.o'))
        self.assertEqual(dlb.fs.Path('a'), dlb.fs.Path('a').with_appended_suffix(''))

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.Path('a').with_appended_suffix(b'.o')
        self.assertEqual("'suffix' must be a str", str(cm.exception))

    def test_fails_for_dot(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('.').with_appended_suffix('a')
        self.assertEqual("cannot append suffix to '.' or '..' component", str(cm.exception))

    def test_fails_for_dotdot(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a/..').with_appended_suffix('a')
        self.assertEqual("cannot append suffix to '.' or '..' component", str(cm.exception))

    def test_fails_for_slash(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a').with_appended_suffix('a/b')
        self.assertEqual("invalid suffix: 'a/b'", str(cm.exception))

    def test_fails_for_nul(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a').with_appended_suffix('a\0b')
        self.assertEqual("invalid suffix: 'a\\x00b'", str(cm.exception))


class WithReplacingSuffixTest(unittest.TestCase):

    def test_typical_is_correct(self):
        self.assertEqual(dlb.fs.Path('a/b.x.o'), dlb.fs.Path('a/b.x.c').with_replacing_suffix('.o'))
        self.assertEqual(dlb.fs.Path('/a/b.x.o.p/'), dlb.fs.Path('/a/b.x.c/').with_replacing_suffix('.o.p'))
        self.assertEqual(dlb.fs.Path('a.o'), dlb.fs.Path('a.').with_replacing_suffix('.o'))
        self.assertEqual(dlb.fs.Path('a'), dlb.fs.Path('a.b').with_replacing_suffix(''))
        self.assertEqual(dlb.fs.Path('ax'), dlb.fs.Path('a.b').with_replacing_suffix('x'))

    def test_fails_without_extension_suffix(self):
        msg = 'does not contain an extension suffix'

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('x').with_replacing_suffix('.o')
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('.bashrc').with_replacing_suffix('.o')
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.Path('a').with_replacing_suffix(b'.o')
        self.assertEqual("'suffix' must be a str", str(cm.exception))

    def test_fails_for_dot(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('.').with_replacing_suffix('a')
        self.assertEqual("cannot append suffix to '.' or '..' component", str(cm.exception))

    def test_fails_for_dotdot(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a/..').with_replacing_suffix('a')
        self.assertEqual("cannot append suffix to '.' or '..' component", str(cm.exception))

    def test_fails_for_slash(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a').with_replacing_suffix('a/b')
        self.assertEqual("invalid suffix: 'a/b'", str(cm.exception))

    def test_fails_for_nul(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a').with_replacing_suffix('a\0b')
        self.assertEqual("invalid suffix: 'a\\x00b'", str(cm.exception))


class RelativeToTest(unittest.TestCase):

    def test_removes_prefix(self):
        p = dlb.fs.Path('../../a/b/c/../d/e/f/').relative_to('../../a/b/')
        self.assertEqual(p, dlb.fs.Path('c/../d/e/f/'))

        p = dlb.fs.Path('../../a/b/c/../d/e/f/').relative_to('.')
        self.assertEqual(p, dlb.fs.Path('../../a/b/c/../d/e/f/'))

        p = dlb.fs.Path('/u/v/w').relative_to('/u/v/')
        self.assertEqual(p, dlb.fs.Path('w'))

        p = dlb.fs.Path('/u/v/w').relative_to('/')
        self.assertEqual(p, dlb.fs.Path('u/v/w'))

    def test_fails_for_nondirectory(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a').relative_to(dlb.fs.Path('b'))
        self.assertEqual("since Path('b') is not a directory, a path cannot be relative to it", str(cm.exception))

    def test_fails_if_other_no_prefix_and_not_collapsable(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a').relative_to(dlb.fs.Path('b/'))
        self.assertEqual("'a' does not start with 'b/'", str(cm.exception))

    def test_starts_with_dotdot_if_other_no_prefix_and_collapsable(self):
        p = dlb.fs.Path('a').relative_to(dlb.fs.Path('b/'), collapsable=True)
        self.assertEqual('../a', p)

        p = dlb.fs.Path('a/b').relative_to(dlb.fs.Path('a/b/c/'), collapsable=True)
        self.assertEqual('..', p)

        p = dlb.fs.Path('/a/b/d').relative_to(dlb.fs.Path('/a/b/c/'), collapsable=True)
        self.assertEqual('../d', p)

    def test_fails_if_only_one_absolute(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('/a/b').relative_to(dlb.fs.Path('a/b/c/'), collapsable=True)
        self.assertEqual("'/a/b' cannot be relative to 'a/b/c/'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('a/b').relative_to(dlb.fs.Path('/a/b/c/'), collapsable=True)
        self.assertEqual("'a/b' cannot be relative to '/a/b/c/'", str(cm.exception))


class PartsAndSliceTest(unittest.TestCase):

    def test_relative_and_absolute_are_different(self):
        p = dlb.fs.Path('u/v/w')
        self.assertEqual(p.parts, ('u', 'v', 'w'))

        p = dlb.fs.Path('/u/v/w')
        self.assertEqual(p.parts, ('/', 'u', 'v', 'w'))

    def test_directory_and_nondirectory_are_equal(self):
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
        self.assertEqual("slice of part indices expected (use 'parts' for single components)", str(cm.exception))


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

    def test_listed_nondirectory_paths_are_complete_and_ordered(self):

        expected_rel_paths = [dlb.fs.Path(s) for s in [
            'a1',
            'b1',
            'b3',
            'b4',
            'b2/c3/d1',
            'b2/c3/d2'
        ]]
        expected_rel_paths.sort()

        paths = self.tmp_dir.list(recurse_name_filter='', is_dir=False)
        rel_paths = self.tmp_dir.list_r(recurse_name_filter='', is_dir=False)
        self.assertEqual(set(rel_paths), set(expected_rel_paths))
        self.assertEqual({p.relative_to(self.tmp_dir) for p in paths}, set(expected_rel_paths))

        self.assertEqual(rel_paths, expected_rel_paths)
        self.assertEqual([p.relative_to(self.tmp_dir) for p in paths], expected_rel_paths)

    def test_listed_directory_paths_are_complete_and_ordered(self):

        expected_rel_paths = [dlb.fs.Path(s) for s in [
            'a2/',
            'b2/',
            'b2/c3/'
        ]]
        expected_rel_paths.sort()

        paths = self.tmp_dir.list(recurse_name_filter='', is_dir=True)
        rel_paths = self.tmp_dir.list_r(recurse_name_filter='', is_dir=True)
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


class NativeComponentsTest(unittest.TestCase):

    def test_has_properties(self):
        nc = dlb.fs._NativeComponents(('', 'a', 'b'), '/')
        self.assertEqual(('', 'a', 'b'), nc.components)
        self.assertEqual('/', nc.sep)

    def test_str_is_correct_for_posix(self):
        self.assertEqual('.', str(dlb.fs._NativeComponents(('',), '/')))
        self.assertEqual('./a\\b/c', str(dlb.fs._NativeComponents(('', 'a\\b', 'c'), '/')))

        self.assertEqual('/', str(dlb.fs._NativeComponents(('/',), '/')))
        self.assertEqual('//', str(dlb.fs._NativeComponents(('//',), '/')))
        self.assertEqual('/a\\b/c', str(dlb.fs._NativeComponents(('/', 'a\\b', 'c'), '/')))
        self.assertEqual('//a\\b/c', str(dlb.fs._NativeComponents(('//', 'a\\b', 'c'), '/')))

    def test_str_is_correct_for_windows(self):
        self.assertEqual('.', str(dlb.fs._NativeComponents(('',), '\\')))
        self.assertEqual('.\\a\\b', str(dlb.fs._NativeComponents(('', 'a', 'b'), '\\')))

        self.assertEqual('C:\\', str(dlb.fs._NativeComponents(('C:\\',), '\\')))
        self.assertEqual('C:\\Windows', str(dlb.fs._NativeComponents(('C:\\', 'Windows'), '\\')))
        self.assertEqual('\\\\u\\r', str(dlb.fs._NativeComponents(('\\\\u\\r',), '\\')))
        self.assertEqual('\\\\u\\r\\t', str(dlb.fs._NativeComponents(('\\\\u\\r', 't'), '\\')))

        # note: the components in the following lines must be avoided by the caller (unsafe)
        self.assertEqual('.\\a:b\\c', str(dlb.fs._NativeComponents(('', 'a:b', 'c'), '\\')))
        self.assertEqual('C:', str(dlb.fs._NativeComponents(('C:',), '\\')))


class NativeTest(unittest.TestCase):

    def test_construction_of_nonnative_keeps_native(self):
        pn = dlb.fs.Path.Native('x/y')
        p = dlb.fs.Path(pn)
        self.assertIs(p.native, pn)

    def test_construction_fails_for_nul(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path.Native('x\0y')
        self.assertEqual("invalid path: ('', 'x\\x00y') (must not contain NUL)", str(cm.exception))

    def test_str_prefixes_relative_with_dot(self):
        s = str(dlb.fs.Path('x').native)
        self.assertEqual(s.replace('\\', '/'), './x')
        self.assertEqual('.', str(dlb.fs.Path('.').native))
        self.assertEqual('..', str(dlb.fs.Path('..').native))

    def test_repr(self):
        p = dlb.fs.Path('x').native
        self.assertIn(os.path.sep, '\\/')
        escaped_sep = '\\\\' if os.path.sep == '\\' else '/'
        self.assertEqual("Path.Native('.{}x')".format(escaped_sep), repr(p))

    def test_is_pathlike(self):
        import os
        p = dlb.fs.Path.Native('x')
        self.assertTrue(isinstance(p, os.PathLike))

    def test_has_same_components_if_relative(self):
        p = dlb.fs.Path('a/b/c')
        n = p.native
        self.assertEqual(p.components, n.components)

    def test_has_same_parts_if_relative(self):
        p = dlb.fs.Path('a/b/c')
        n = p.native
        self.assertEqual(p.parts, n.parts)

    def test_restrictions_are_checked_exactly_once_when_converted_to_native(self):

        class CheckCountingPath(dlb.fs.Path):
            n = 0

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            # noinspection PyUnusedLocal
            def check_restriction_to_base(self, components_checked: bool):
                self.__class__.n += 1

        p = CheckCountingPath('x')
        self.assertEqual(1, CheckCountingPath.n)

        p = CheckCountingPath(p)
        self.assertEqual(1, CheckCountingPath.n)

        p = CheckCountingPath(dlb.fs.Path(p))
        self.assertEqual(2, CheckCountingPath.n)

        p.native
        self.assertEqual(2, CheckCountingPath.n)

        CheckCountingPath.Native('x')
        self.assertEqual(3, CheckCountingPath.n)

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


@unittest.skipUnless(isinstance(pathlib.Path(), pathlib.WindowsPath), 'requires MS Windows')
class NativeWindowsTest(unittest.TestCase):

    def test_constructor_fails_for_invalid_path(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path.Native('a:b')
        msg = "'path' is neither relative nor absolute"
        self.assertEqual(msg, str(cm.exception))

        p = pathlib.Path('a') / "*" / ":"
        self.assertEqual(('a', '*', ':'), dlb.fs.Path.Native(p).parts)


class CopyTest(unittest.TestCase):

    def test_can_copy(self):
        for p in [dlb.fs.Path('a'), dlb.fs.Path.Native('a'), dlb.fs.Path(dlb.fs.Path.Native('a'))]:
            copy.copy(p)

    def test_can_deepcopy(self):
        for p in [dlb.fs.Path('a'), dlb.fs.Path.Native('a'), dlb.fs.Path(dlb.fs.Path.Native('a'))]:
            copy.deepcopy(p)


class PickleTest(unittest.TestCase):

    def test_can_be_pickled(self):
        import pickle
        f = dlb.fs.Path('a/b/c')

        pf = pickle.dumps(f)
        f.native
        pfn = pickle.dumps(pf)
        pd = pickle.dumps(dlb.fs.Path('a/b/c/'))

        self.assertNotEqual(pf, pfn)  # includes native representation
        self.assertNotEqual(pf, pd)


class RelativeRestrictionsTest(unittest.TestCase):

    def test_relative_permitted(self):
        dlb.fs.RelativePath('a/b/c')

    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.RelativePath('/a/b/c')
        self.assertEqual("invalid path for 'RelativePath': '/a/b/c' (must be relative)", str(cm.exception))


class AbsoluteRestrictionsTest(unittest.TestCase):

    def test_absolute_permitted(self):
        dlb.fs.AbsolutePath('/a/b/c')

    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.AbsolutePath('a/b/c')
        self.assertEqual("invalid path for 'AbsolutePath': 'a/b/c' (must be absolute)", str(cm.exception))


class NormalizedRestrictionsTest(unittest.TestCase):

    def test_relative_permitted(self):
        dlb.fs.NormalizedPath('/a/b/c')

    def test_absolute_permitted(self):
        dlb.fs.NormalizedPath('/a/b/c')

    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.NormalizedPath('a/../b')
        self.assertEqual("invalid path for 'NormalizedPath': 'a/../b' (must be normalized)", str(cm.exception))


class NoSpaceRestrictionsTest(unittest.TestCase):

    def test_fails_for_space(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.NoSpacePath('a b')
        self.assertEqual("invalid path for 'NoSpacePath': 'a b' (must not contain space)", str(cm.exception))


class PosixRestrictionsTest(unittest.TestCase):

    def test_fails_for_nul(self):
        # IEEE Std 1003.1-2008, §3.170
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PosixPath('a\x00b')
        self.assertEqual("invalid path: 'a\\x00b' (must not contain NUL)", str(cm.exception))


class PortablePosixRestrictionsTest(unittest.TestCase):

    def test_fails_for_slashslash(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('//unc/root/d')
        msg = (
            "invalid path for 'PortablePosixPath': '//unc/root/d' "
            "(non-standardized component starting with '//' not allowed)"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_leading_dash(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('/a/-b')
        msg = "invalid path for 'PortablePosixPath': '/a/-b' (component must not start with '-')"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_backslash(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('a\\b')
        msg = r"invalid path for 'PortablePosixPath': 'a\\b' (must not contain these characters: '\\')"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_too_long_component(self):
        dlb.fs.PortablePosixPath('a' * dlb.fs.PortablePosixPath.MAX_COMPONENT_LENGTH)
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('a' * (dlb.fs.PortablePosixPath.MAX_COMPONENT_LENGTH + 1))
        msg = (
            "invalid path for 'PortablePosixPath': 'aaaaaaaaaaaaaaa' "
            "(component must not contain more than 14 characters)"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_too_long(self):
        dlb.fs.PortablePosixPath('a/' * (dlb.fs.PortablePosixPath.MAX_PATH_LENGTH // 2) + 'b')

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('a/' * (dlb.fs.PortablePosixPath.MAX_PATH_LENGTH // 2) + 'bc')
        self.assertTrue(str(cm.exception).endswith(" (must not contain more than 255 characters)"))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortablePosixPath('a/' * (dlb.fs.PortablePosixPath.MAX_PATH_LENGTH // 2) + 'b/')
        self.assertTrue(str(cm.exception).endswith(" (must not contain more than 255 characters)"))


class PortablePosixPathSubclassTest(unittest.TestCase):

    def test_redefined_class_attribute_are_ignored(self):
        # As the representative for the use of class attributes in subclasses of dlb.fs.Path

        class PPath(dlb.fs.PortablePosixPath):
            MAX_COMPONENT_LENGTH = 2

        PPath('xyz')  # uses still dlb.fs.PortablePosixPath.MAX_COMPONENT_LENGTH


class WindowsRestrictionsTest(unittest.TestCase):

    def test_fails_for_backslash(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a\\b')
        self.assertEqual("invalid path for 'WindowsPath': 'a\\\\b' (must not contain reserved characters: '\\\\')",
                         str(cm.exception))

    def test_fails_for_nul(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a\x00b')
        self.assertEqual("invalid path: 'a\\x00b' (must not contain NUL)", str(cm.exception))

    def test_fails_for_control_character(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a\nb')
        self.assertEqual(
            "invalid path for 'WindowsPath': 'a\\nb' "
            "(must not contain characters with codepoint lower than U+0020: U+000A)",
            str(cm.exception))

    def test_fails_for_non_bmp_character(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('a\U00010000b')
        self.assertEqual(
            "invalid path for 'WindowsPath': 'a\U00010000b' "
            "(must not contain characters with codepoint higher than U+FFFF: U+10000)",
            str(cm.exception))

    def test_fails_for_nondrive_colon(self):
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

    def test_fails_for_star(self):
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

    def test_fails_for_nonrelative_without_root(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('/')
        self.assertEqual("invalid path for 'WindowsPath': '/' (neither absolute nor relative: root is missing)",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.WindowsPath('/a:b')
        self.assertEqual("invalid path for 'WindowsPath': '/a:b' (neither absolute nor relative: drive is missing)",
                         str(cm.exception))

    def test_fails_for_reserved_file(self):
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

    def test_fails_for_space_at_end_of_component(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('a/b /c')
        self.assertEqual("invalid path for 'PortableWindowsPath': 'a/b /c' (component must not end with ' ' or '.')",
                         str(cm.exception))

    def test_fails_for_dot_at_end_of_component(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('a/b./c')
        self.assertEqual("invalid path for 'PortableWindowsPath': 'a/b./c' (component must not end with ' ' or '.')",
                         str(cm.exception))
        dlb.fs.PortablePath('a/../c')

    def test_fails_for_too_long_component(self):
        dlb.fs.PortableWindowsPath('a' * dlb.fs.PortableWindowsPath.MAX_COMPONENT_LENGTH)

        with self.assertRaises(ValueError) as cm:
            dlb.fs.PortableWindowsPath('a' * (dlb.fs.PortableWindowsPath.MAX_COMPONENT_LENGTH + 1))

        self.assertTrue(str(cm.exception).endswith(" (component must not contain more than 255 characters)"))

    def test_fails_for_too_long(self):
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


def sleep_until_mtime_change():
    import time
    import tempfile

    t0 = time.monotonic_ns()
    with tempfile.TemporaryDirectory() as tmp_dir_path:
        p = os.path.join(tmp_dir_path, 't')
        open(p, 'x').close()

        mtime0 = os.lstat(p).st_mtime_ns
        while True:
            assert (time.monotonic_ns() - t0) / 1e9 <= 10.0
            time.sleep(15e-3)
            with open(p, 'w') as f:
                f.write('1')
            mtime = os.lstat(p).st_mtime_ns
            if mtime != mtime0:
                break


class PropagateMtimeTest(testenv.TemporaryDirectoryTestCase):

    def test_scenario1(self):
        os.mkdir('d')
        os.mkdir(os.path.join('d', 'a'))
        os.mkdir(os.path.join('d', 'b'))
        open(os.path.join('d', 'b', 'c'), 'x').close()
        open(os.path.join('d', 'b', 'd'), 'x').close()
        dlb.fs.Path('d/').propagate_mtime()  # may or may not update mtime

        self.assertIsNone(dlb.fs.Path('d/').propagate_mtime())

        sleep_until_mtime_change()
        with open(os.path.join('d', 'b', 'd'), 'w') as f:
            f.write('1')
        sleep_until_mtime_change()
        with open(os.path.join('d', 'b', 'c'), 'w') as f:
            f.write('2')
        mtime_ns = os.lstat(os.path.join('d', 'b', 'c')).st_mtime_ns

        self.assertEqual(mtime_ns, dlb.fs.Path('d/').propagate_mtime())
        self.assertEqual(mtime_ns, os.lstat('d').st_mtime_ns)
        self.assertEqual(mtime_ns, os.lstat(os.path.join('d', 'b')).st_mtime_ns)

        self.assertIsNone(dlb.fs.Path('d/').propagate_mtime())

    def test_none_for_empty(self):
        os.mkdir('d')
        self.assertIsNone(dlb.fs.Path('d/').propagate_mtime())

    def test_ignores_filtered(self):
        os.mkdir('d')
        os.mkdir(os.path.join('d', 'a'))
        open(os.path.join('d', 'a', 'c'), 'x').close()
        os.mkdir(os.path.join('d', 'b'))
        open(os.path.join('d', 'b', 'd'), 'x').close()
        dlb.fs.Path('d/').propagate_mtime()  # may or may not update mtime

        sleep_until_mtime_change()
        with open(os.path.join('d', 'a', 'c'), 'w') as f:
            f.write('1')
        self.assertIsNone(dlb.fs.Path('d/').propagate_mtime(recurse_name_filter='b.*'))

        os.mkdir(os.path.join('d', 'a', 'e'))  # updates directory itself
        os.lstat(os.path.join('d', 'a'))  # necessary on MS Windows, for whatever reason, to update mtime

        self.assertIsNotNone(dlb.fs.Path('d/').propagate_mtime(recurse_name_filter='b.*'))

        sleep_until_mtime_change()
        with open(os.path.join('d', 'a', 'c'), 'w') as f:
            f.write('2')
        self.assertIsNone(dlb.fs.Path('d/').propagate_mtime(name_filter='[^c].*'))
        self.assertIsNotNone(dlb.fs.Path('d/').propagate_mtime())

    def test_ignores_subdirectory_without_match(self):
        os.mkdir('d')
        sleep_until_mtime_change()
        os.mkdir(os.path.join('d', 'b'))
        open(os.path.join('d', 'b', 'c'), 'x').close()
        sleep_until_mtime_change()
        with open(os.path.join('d', 'b', 'c'), 'w') as f:
            f.write('1')

        self.assertIsNone(dlb.fs.Path('d/').propagate_mtime(name_filter='x', recurse_name_filter=''))
        self.assertIsNotNone(dlb.fs.Path('d/').propagate_mtime(name_filter='c', recurse_name_filter=''))

        sleep_until_mtime_change()
        open(os.path.join('d', 'b', 'd'), 'x').close()

        self.assertIsNone(dlb.fs.Path('d/').propagate_mtime(name_filter='x', recurse_name_filter=''))
        self.assertIsNotNone(dlb.fs.Path('d/').propagate_mtime(name_filter='b', recurse_name_filter=''))

    def test_fails_for_nondirectory(self):
        open('f', 'xb').close()
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('f').propagate_mtime()
        self.assertEqual("cannot list non-directory path: 'f'", str(cm.exception))

    def test_fails_for_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            dlb.fs.Path('d/').propagate_mtime()

    @unittest.skipUnless(sys.platform != 'win32', 'requires POSIX filesystem')
    def test_does_not_change_atime(self):
        os.mkdir('d')
        open(os.path.join('d', 'a'), 'x').close()
        sr0 = os.lstat('d')

        sleep_until_mtime_change()
        with open(os.path.join('d', 'a'), 'w') as f:
            f.write('1')

        mtime_ns = dlb.fs.Path('d/').propagate_mtime()
        self.assertGreater(mtime_ns, sr0.st_mtime_ns)
        sr = os.lstat('d')
        self.assertEqual(sr.st_mtime_ns, mtime_ns)
        self.assertEqual(sr.st_atime_ns, sr0.st_atime_ns)


class FindLatestMtimeTest(testenv.TemporaryDirectoryTestCase):

    def test_scenario1(self):
        os.mkdir('d')
        sleep_until_mtime_change()
        open(os.path.join('d', 'x'), 'x').close()
        sleep_until_mtime_change()
        os.mkdir(os.path.join('d', 'a'))
        sleep_until_mtime_change()
        open(os.path.join('d', 'a', 'y'), 'x').close()
        sleep_until_mtime_change()
        os.mkdir(os.path.join('d', 'a', 'b'))
        sleep_until_mtime_change()
        open(os.path.join('d', 'a', 'b', 'z'), 'x').close()
        sleep_until_mtime_change()
        with open(os.path.join('d', 'a', 'b', 'z'), 'w') as f:
            f.write('1')

        self.assertEqual(dlb.fs.Path('d/a/'), dlb.fs.Path('d/').find_latest_mtime())
        self.assertEqual(dlb.fs.Path('d/a/'), dlb.fs.Path('d/').find_latest_mtime(is_dir=True))
        self.assertEqual(dlb.fs.Path('d/x'), dlb.fs.Path('d/').find_latest_mtime(is_dir=False))

        self.assertEqual(dlb.fs.Path('d/a/b/z'), dlb.fs.Path('d/').find_latest_mtime(recurse_name_filter=''))
        self.assertEqual(dlb.fs.Path('d/a/b/'),
                         dlb.fs.Path('d/').find_latest_mtime(is_dir=True, recurse_name_filter=''))
        self.assertEqual(dlb.fs.Path('d/a/b/z'),
                         dlb.fs.Path('d/').find_latest_mtime(is_dir=False, recurse_name_filter=''))

    def test_empty_returns_none_if_empty(self):
        os.mkdir('d')
        self.assertIsNone(dlb.fs.Path('d/').find_latest_mtime())
        self.assertIsNone(dlb.fs.Path('d/').find_latest_mtime(is_dir=False))
        self.assertIsNone(dlb.fs.Path('d/').find_latest_mtime(is_dir=True))

    def test_returns_smaller_for_same_mtime(self):
        open('a', 'x').close()
        open('b', 'x').close()
        os.utime('a', ns=(123, 456))
        os.utime('b', ns=(123, 456))
        self.assertEqual(dlb.fs.Path('a'), dlb.fs.Path('.').find_latest_mtime())

    def test_fails_for_nondirectory(self):
        open('f', 'xb').close()
        with self.assertRaises(ValueError) as cm:
            dlb.fs.Path('f').find_latest_mtime()
        self.assertEqual("cannot list non-directory path: 'f'", str(cm.exception))

    def test_fails_for_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            dlb.fs.Path('d/').find_latest_mtime()
