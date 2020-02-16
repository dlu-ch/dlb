# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.fs.manip
import pathlib
import tempfile
import collections
import unittest
import tools_for_test


class RemoveFilesystemObjectTest(tools_for_test.TemporaryDirectoryTestCase):

    @staticmethod
    def create_dir_a_in_cwd(all_writable=True):
        os.makedirs(os.path.join('a', 'b1', 'c', 'd1'))
        os.makedirs(os.path.join('a', 'b1', 'c', 'd2'))
        os.makedirs(os.path.join('a', 'b1', 'c', 'd3'))
        os.makedirs(os.path.join('a', 'b2'))
        os.makedirs(os.path.join('a', 'b3', 'c'))
        if not all_writable:
            os.chmod(os.path.join('a',  'b1', 'c'), 0o000)

    def test_fails_for_relative_path(self):
        with open('x', 'wb'):
            pass

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object('x')
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object(pathlib.Path('x'))
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object(dlb.fs.Path('x'))
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        self.assertTrue(os.path.isfile('x'))  # still exists

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object('')
        self.assertEqual("not an absolute path: ''", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object(pathlib.Path(''))
        self.assertEqual("not an absolute path: '.'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.remove_filesystem_object(dlb.fs.Path('.'))
        self.assertEqual("not an absolute path: '.'", str(cm.exception))

    # noinspection PyTypeChecker
    def test_fails_for_bytes_path(self):
        with open('x', 'wb'):
            pass

        with self.assertRaises(TypeError) as cm:
            dlb.fs.manip.remove_filesystem_object(b'x')
        self.assertEqual("'abs_path' must be a str, pathlib.Path or dlb.fs.Path object, not bytes", str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.fs.manip.remove_filesystem_object('x', abs_empty_dir_path=b'x')
        msg = "'abs_empty_dir_path' must be a str, pathlib.Path or dlb.fs.Path object, not bytes"
        self.assertEqual(msg, str(cm.exception))

    def test_removes_existing_regular_file(self):
        with open('f', 'wb'):
            pass

        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'f'))

        self.assertFalse(os.path.exists('f'))

    def test_removes_empty_directory(self):
        os.mkdir('d')

        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'd'))

        self.assertFalse(os.path.exists('d'))

    def test_removes_symbolic_link(self):
        with open('f', 'wb'):
            pass

        try:
            os.symlink('f', 's', target_is_directory=False)
            self.assertTrue(os.path.islink('s'))
        except (NotImplementedError, PermissionError):  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 's'))
        self.assertFalse(os.path.exists('s'))
        self.assertTrue(os.path.exists('f'))  # still exists

    def test_fails_for_nonexisting(self):
        with self.assertRaises(FileNotFoundError):
            dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'n'))

    def test_ignores_for_nonexisting_if_required(self):
        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'n'), ignore_non_existing=True)

    def test_removes_nonempty_directory_in_place(self):
        self.create_dir_a_in_cwd()
        dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'a'))
        self.assertFalse(os.path.exists('a'))

    def test_removes_nonempty_directory_in_tmp(self):
        self.create_dir_a_in_cwd()
        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.fs.manip.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.abspath(abs_temp_dir_path))
        self.assertFalse(os.path.exists('a'))

    def test_removes_most_of_nonempty_directory_in_place_if_permission_denied_in_subdirectory(self):
        self.create_dir_a_in_cwd(all_writable=False)

        with self.assertRaises(PermissionError):
            try:
                dlb.fs.manip.remove_filesystem_object(os.path.join(os.getcwd(), 'a'))
            finally:
                os.chmod(os.path.join('a', 'b1', 'c'), 0o777)

        self.assertTrue(os.path.exists('a'))  # still exists

    def test_removes_nonempty_directory_in_tmp_if_permission_denied_in_subdirectory(self):
        self.create_dir_a_in_cwd(all_writable=False)

        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.fs.manip.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.abspath(abs_temp_dir_path))
            os.chmod(os.path.join(abs_temp_dir_path, 't', 'b1', 'c'), 0o777)

        self.assertFalse(os.path.exists('a'))  # was successful


class ReadFilesystemObjectMemoTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_relative_path(self):
        with open('x', 'wb'):
            pass

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.read_filesystem_object_memo('x')
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.read_filesystem_object_memo(pathlib.Path('x'))
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.read_filesystem_object_memo(dlb.fs.Path('x'))
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

    def test_fails_for_bytes_path(self):
        with open('x', 'wb'):
            pass

        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.read_filesystem_object_memo(b'x')
        self.assertEqual("'abs_path' must be a str or path, not bytes", str(cm.exception))

    def test_return_none_for_nonexisting(self):
        m, sr = dlb.fs.manip.read_filesystem_object_memo(os.path.join(os.getcwd(), 'x'))
        self.assertIsInstance(m, dlb.fs.manip.FilesystemObjectMemo)
        self.assertIsNone(sr)
        self.assertIsNone(m.stat)
        self.assertIsNone(m.symlink_target)

    def test_return_stat_for_existing_regular(self):
        with open('x', 'wb'):
            pass

        sr0 = os.lstat('x')

        m, sr = dlb.fs.manip.read_filesystem_object_memo(os.path.join(os.getcwd(), 'x'))
        self.assertIsInstance(m, dlb.fs.manip.FilesystemObjectMemo)
        self.assertIsInstance(sr, os.stat_result)

        self.assertEqual(sr0.st_mode, m.stat.mode)
        self.assertEqual(sr0.st_size, m.stat.size)
        self.assertEqual(sr0.st_mtime_ns, m.stat.mtime_ns)
        self.assertEqual(sr0.st_uid, m.stat.uid)
        self.assertEqual(sr0.st_gid, m.stat.gid)
        self.assertIsNone(m.symlink_target)
        self.assertEqual(sr0, sr)

    def test_return_stat_and_target_for_existing_directory_for_str(self):
        os.mkdir('d')
        os.chmod('d', 0x000)
        try:
            os.symlink('d' + os.path.sep, 's', target_is_directory=True)
            # note: trailing os.path.sep is necessary irrespective of target_is_directory

            sr0 = os.lstat('s')
            m, sr = dlb.fs.manip.read_filesystem_object_memo(os.path.join(os.getcwd(), 's'))
            self.assertIsInstance(m, dlb.fs.manip.FilesystemObjectMemo)
            self.assertIsInstance(sr, os.stat_result)

            self.assertEqual(sr0.st_mode, m.stat.mode)
            self.assertEqual(m.symlink_target, 'd' + os.path.sep)
            self.assertEqual(sr0, sr)

        finally:
            os.chmod('d', 0x777)

    def test_return_stat_and_target_for_existing_directory_for_pathlib(self):
        os.mkdir('d')
        os.chmod('d', 0x000)
        try:
            os.symlink('d' + os.path.sep, 's', target_is_directory=True)
            # note: trailing os.path.sep is necessary irrespective of target_is_directory

            sr0 = os.lstat('s')
            m, sr = dlb.fs.manip.read_filesystem_object_memo(pathlib.Path(os.path.join(os.getcwd()) / pathlib.Path('s')))
            self.assertIsInstance(m, dlb.fs.manip.FilesystemObjectMemo)
            self.assertIsInstance(sr, os.stat_result)

            self.assertEqual(sr0.st_mode, m.stat.mode)
            self.assertIsInstance(m.symlink_target, str)
            self.assertEqual(m.symlink_target, 'd' + os.path.sep)

        finally:
            os.chmod('d', 0x777)


class NormalizeDotDotPureTest(unittest.TestCase):

    def test_relative_is_correct(self):
        for P in (dlb.fs.PortablePath, pathlib.Path, pathlib.PureWindowsPath):
            p = dlb.fs.manip.normalize_dotdot_pure(P('a/b/c'))
            self.assertEqual(P('a/b/c'), p, repr(P))

            p = dlb.fs.manip.normalize_dotdot_pure(P('a/b/c/'))
            self.assertEqual(P('a/b/c/'), p, repr(P))

            p = dlb.fs.manip.normalize_dotdot_pure(P('a/../b/c/..'))
            self.assertEqual(P('b/'), p, repr(P))

            p = dlb.fs.manip.normalize_dotdot_pure(P('a/b/../../'))
            self.assertEqual(P('.'), p, repr(P))

            p = dlb.fs.manip.normalize_dotdot_pure(P('a/b/../../a'))
            self.assertEqual(P('a'), p, repr(P))

    def test_same_instance_if_unchanged(self):
        p = dlb.fs.PortablePath('a/b/c')
        self.assertIs(p, dlb.fs.manip.normalize_dotdot_pure(p))

        p = pathlib.PureWindowsPath('a/b/c')
        self.assertIs(p, dlb.fs.manip.normalize_dotdot_pure(p))

    def test_absolute_is_correct(self):
        # noinspection PyPep8Naming
        P = pathlib.PurePosixPath

        p = dlb.fs.manip.normalize_dotdot_pure(P('/tmp/../x'))
        self.assertEqual(P('/x'), p)

        p = dlb.fs.manip.normalize_dotdot_pure(P('/tmp/../x/..'))
        self.assertEqual(P('/'), p)

        # noinspection PyPep8Naming
        P = pathlib.PureWindowsPath

        p = dlb.fs.manip.normalize_dotdot_pure(P(r'C:\\Windows\\Temp\\..'))
        self.assertEqual(P('C:\\Windows\\'), p)

        p = dlb.fs.manip.normalize_dotdot_pure(P(r'C:\\Windows\\..\\Temp\\..'))
        self.assertEqual(P('C:\\'), p)

    def test_return_same_type(self):
        isinstance(dlb.fs.manip.normalize_dotdot_pure(pathlib.PurePosixPath('a/b')),
                   pathlib.PurePosixPath)
        isinstance(dlb.fs.manip.normalize_dotdot_pure(pathlib.PureWindowsPath('a/b')),
                   pathlib.PureWindowsPath)
        isinstance(dlb.fs.manip.normalize_dotdot_pure(dlb.fs.Path('a/b')),
                   dlb.fs.Path)
        isinstance(dlb.fs.manip.normalize_dotdot_pure(dlb.fs.NoSpacePath('a/b')),
                   dlb.fs.NoSpacePath)

    def test_fails_for_str(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot_pure(b'a/b')
        msg = "'path' must be a dlb.fs.Path or pathlib.PurePath object"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot_pure(b'a/b')
        msg = "'path' must be a dlb.fs.Path or pathlib.PurePath object"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_upwards_path(self):
        with self.assertRaises(dlb.fs.manip.PathNormalizationError):
            dlb.fs.manip.normalize_dotdot_pure(dlb.fs.Path('..'))
        with self.assertRaises(dlb.fs.manip.PathNormalizationError):
            dlb.fs.manip.normalize_dotdot_pure(dlb.fs.Path('a/../../b/a/b'))
        with self.assertRaises(dlb.fs.manip.PathNormalizationError):
            dlb.fs.manip.normalize_dotdot_pure(pathlib.PurePosixPath(r'/tmp/../..'))
        with self.assertRaises(dlb.fs.manip.PathNormalizationError) as cm:
            dlb.fs.manip.normalize_dotdot_pure(pathlib.PureWindowsPath(r'C:\\Windows\\..\\Temp\\..\\..'))
        msg = "is an upwards path: PureWindowsPath('C:/Windows/../Temp/../..')"
        self.assertEqual(msg, str(cm.exception))


class NormalizeDotDotFsTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_without_symlink_is_correct(self):
        os.makedirs('a')
        os.makedirs('c/d/e')
        p = dlb.fs.manip.normalize_dotdot(dlb.fs.Path('a/../c/d/e/..'), ref_dir_path=pathlib.Path.cwd())
        self.assertEqual(dlb.fs.Path('c/d/'), p)

    def test_with_nonparent_symlink_is_correct(self):
        os.makedirs('a')
        os.makedirs('x/d/e')
        os.symlink('x', 'c', target_is_directory=True)
        p = dlb.fs.manip.normalize_dotdot(dlb.fs.Path('a/../c/d/e/..'), ref_dir_path=pathlib.Path.cwd())
        self.assertEqual(dlb.fs.Path('c/d/'), p)

    def test_fails_for_str(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot(pathlib.PosixPath('a/b'), '/tmp')
        msg = "'ref_dir_path' must be a dlb.fs.Path or pathlib.Path object"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot(pathlib.PosixPath('a/b'), b'/tmp')
        msg = "'ref_dir_path' must be a dlb.fs.Path or pathlib.Path object"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_purepath(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot(pathlib.PureWindowsPath('C:/a/b'), '/tmp')
        msg = "'path' must be a dlb.fs.Path or pathlib.Path object"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_relative_ref_dir(self):
        with self.assertRaises(ValueError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot(pathlib.PosixPath('a/b'), pathlib.PosixPath('tmp'))
        msg = "'ref_dir_path' must be absolute"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_nonexisting_symlink(self):
        os.makedirs('a')
        os.makedirs('c/d')
        regex = r"\Acheck failed with FileNotFoundError: '.+'\Z"
        with self.assertRaisesRegex(dlb.fs.manip.PathNormalizationError, regex):
            dlb.fs.manip.normalize_dotdot(dlb.fs.Path('a/../c/d/e/..'), ref_dir_path=pathlib.Path.cwd())

    def test_fails_for_parent_symlink(self):
        os.makedirs('x')
        os.makedirs('c/d')
        os.symlink('x', 'a', target_is_directory=True)
        regex = r"\Anot a collapsable path, since this is a symbolic link: '.+'\Z"
        with self.assertRaisesRegex(dlb.fs.manip.PathNormalizationError, regex):
            dlb.fs.manip.normalize_dotdot(dlb.fs.Path('a/../c/d/e/..'), ref_dir_path=pathlib.Path.cwd())


class BuildNormalPathOfExistingTest(tools_for_test.TemporaryDirectoryTestCase):
    def test_is_correct_for_normal_relative(self):
        os.makedirs('a/b/c')

        for P in (dlb.fs.Path, pathlib.Path):
            p, memo, sr = dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                P('a/b/c'),
                ref_dir_real_native_path=os.getcwd())
            self.assertEqual(P('a/b/c'), p, repr(P))
            self.assertIsInstance(memo, dlb.fs.manip.FilesystemObjectMemo)
            self.assertIsNotNone(sr)

    def test_is_correct_for_nonnormal_relative_without_symlink(self):
        os.makedirs('a/b')
        os.makedirs('a/c')
        os.makedirs('a/d/e')

        for P in (dlb.fs.Path, pathlib.Path):
            p, _, _ = dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                P('a/b/../c/../d/e'),
                ref_dir_real_native_path=os.getcwd())
            self.assertEqual(P('a/d/e'), p, repr(P))

    def test_is_correct_for_normal_relative_with_symlink(self):
        os.makedirs('x/b/c')
        os.makedirs('c/d')
        os.symlink('x', 'a', target_is_directory=True)

        for P in (dlb.fs.Path, pathlib.Path):
            p, _, _ = dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                P('a/b/c'),
                ref_dir_real_native_path=os.getcwd())
            self.assertEqual(P('x/b/c'), p, repr(P))

    def test_is_correct_for_refdir(self):
        for P in (dlb.fs.Path, pathlib.Path):
            p, _, _ = dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                P(pathlib.Path.cwd()),
                ref_dir_real_native_path=os.getcwd())
            self.assertEqual(P('.'), p, repr(P))

    def test_fails_for_str(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                'a/b', ref_dir_real_native_path='/tmp')
        msg = "'path' must be a dlb.fs.Path or pathlib.Path object"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                b'a/b', ref_dir_real_native_path='/tmp')
        msg = "'path' must be a dlb.fs.Path or pathlib.Path object"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_purepath(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                pathlib.PureWindowsPath('C:/Windows'),
                ref_dir_real_native_path='/tmp')
        msg = "'path' must be a dlb.fs.Path or pathlib.Path object"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_nonstr_reference(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                dlb.fs.Path('a/b'),
                ref_dir_real_native_path=dlb.fs.Path('/tmp'))
        msg = "'ref_dir_real_native_path' must be a str"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                dlb.fs.Path('a/b'),
                ref_dir_real_native_path=b'/tmp')
        msg = "'ref_dir_real_native_path' must be a str"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_relative_reference(self):
        with self.assertRaises(ValueError) as cm:
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                dlb.fs.Path('a/b'),
                ref_dir_real_native_path='.')
        msg = "'ref_dir_real_native_path' must be absolute"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_partial_prefix(self):
        os.makedirs('a/bc/d')

        regex = r"\A()does not exist: '.+'\Z"
        with self.assertRaisesRegex(dlb.fs.manip.PathNormalizationError, regex):
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                pathlib.Path('a/b'),
                ref_dir_real_native_path=os.getcwd())

    def test_fails_if_no_prefix(self):
        os.makedirs('a')

        regex = r"\A'path' not in reference directory, check exact letter case: .+\Z"
        with self.assertRaisesRegex(dlb.fs.manip.PathNormalizationError, regex):
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                pathlib.Path(pathlib.Path.cwd()),
                ref_dir_real_native_path=os.path.join(os.getcwd(), 'a'))

        regex = r"\A'path' not in reference directory: .+\Z"
        with self.assertRaisesRegex(dlb.fs.manip.PathNormalizationError, regex):
            dlb.fs.manip.normalize_dotdot_with_memo_relative_to(
                pathlib.Path('..'),
                ref_dir_real_native_path=os.path.join(os.getcwd(), 'a'))
