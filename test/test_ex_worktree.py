# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex.worktree
import tempfile
import unittest
import tools_for_test


class FilenamePortabilityTest(unittest.TestCase):

    def test_management_tree_paths_are_portable(self):
        import dlb.fs
        dlb.fs.PortablePath(dlb.ex.worktree.MANAGEMENTTREE_DIR_NAME)
        dlb.fs.PortablePath(dlb.ex.worktree.MTIME_PROBE_FILE_NAME)
        dlb.fs.PortablePath(dlb.ex.worktree.RUNDB_FILE_NAME)


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
            dlb.ex.worktree.remove_filesystem_object('x')
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex.worktree.remove_filesystem_object(dlb.fs.Path('x'))
        escaped_sep = '\\\\' if os.path.sep == '\\' else '/'
        self.assertEqual("not an absolute path: '.{}x'".format(escaped_sep), str(cm.exception))

        self.assertTrue(os.path.isfile('x'))  # still exists

        with self.assertRaises(ValueError) as cm:
            dlb.ex.worktree.remove_filesystem_object('')
        self.assertEqual("not an absolute path: ''", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex.worktree.remove_filesystem_object(dlb.fs.Path('.'))
        self.assertEqual("not an absolute path: '.'", str(cm.exception))

    # noinspection PyTypeChecker
    def test_fails_for_bytes_path(self):
        with open('x', 'wb'):
            pass

        with self.assertRaises(TypeError) as cm:
            dlb.ex.worktree.remove_filesystem_object(b'x')
        self.assertEqual("'abs_path' must be a str or dlb.fs.Path object, not bytes", str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.ex.worktree.remove_filesystem_object('/tmp/x', abs_empty_dir_path=b'x')
        msg = "'abs_empty_dir_path' must be a str or dlb.fs.Path object, not bytes"
        self.assertEqual(msg, str(cm.exception))

    def test_removes_existing_regular_file(self):
        with open('f', 'wb'):
            pass

        dlb.ex.worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'f'))

        self.assertFalse(os.path.exists('f'))

    def test_removes_empty_directory(self):
        os.mkdir('d')

        dlb.ex.worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'd'))

        self.assertFalse(os.path.exists('d'))

    def test_removes_symbolic_link(self):
        with open('f', 'wb'):
            pass

        try:
            os.symlink('f', 's', target_is_directory=False)
            self.assertTrue(os.path.islink('s'))
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        dlb.ex.worktree.remove_filesystem_object(os.path.join(os.getcwd(), 's'))
        self.assertFalse(os.path.exists('s'))
        self.assertTrue(os.path.exists('f'))  # still exists

    def test_fails_for_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            dlb.ex.worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'n'))

    def test_ignores_for_nonexistent_if_required(self):
        dlb.ex.worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'n'), ignore_non_existent=True)

    def test_fails_for_relative_tmp(self):
        self.create_dir_a_in_cwd()
        with self.assertRaises(ValueError):
            dlb.ex.worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'a'), abs_empty_dir_path='a')

    def test_removes_nonempty_directory_in_place(self):
        self.create_dir_a_in_cwd()
        dlb.ex.worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'a'))
        self.assertFalse(os.path.exists('a'))

    def test_removes_nonempty_directory_in_tmp(self):
        self.create_dir_a_in_cwd()
        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.ex.worktree.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.abspath(abs_temp_dir_path))
        self.assertFalse(os.path.exists('a'))

    def test_removes_most_of_nonempty_directory_in_place_if_permission_denied_in_subdirectory(self):
        self.create_dir_a_in_cwd(all_writable=False)

        with self.assertRaises(PermissionError):
            try:
                dlb.ex.worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'a'))
            finally:
                os.chmod(os.path.join('a', 'b1', 'c'), 0o777)

        self.assertTrue(os.path.exists('a'))  # still exists

    def test_removes_nonempty_directory_in_tmp_if_permission_denied_in_subdirectory(self):
        self.create_dir_a_in_cwd(all_writable=False)

        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.ex.worktree.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.abspath(abs_temp_dir_path))
            os.chmod(os.path.join(abs_temp_dir_path, 't', 'b1', 'c'), 0o777)

        self.assertFalse(os.path.exists('a'))  # was successful


class ReadFilesystemObjectMemoTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_relative_path(self):
        with open('x', 'wb'):
            pass

        with self.assertRaises(ValueError) as cm:
            dlb.ex.worktree.read_filesystem_object_memo('x')
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex.worktree.read_filesystem_object_memo(dlb.fs.Path('x'))
        escaped_sep = '\\\\' if os.path.sep == '\\' else '/'
        self.assertEqual("not an absolute path: '.{}x'".format(escaped_sep), str(cm.exception))

    def test_fails_for_bytes_path(self):
        with open('x', 'wb'):
            pass

        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.worktree.read_filesystem_object_memo(b'x')
        self.assertEqual("'abs_path' must be a str or path, not bytes", str(cm.exception))

    def test_fails_for_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            dlb.ex.worktree.read_filesystem_object_memo(os.path.join(os.getcwd(), 'x'))

    def test_return_stat_for_existing_regular(self):
        with open('x', 'wb'):
            pass

        sr0 = os.lstat('x')

        m = dlb.ex.worktree.read_filesystem_object_memo(os.path.join(os.getcwd(), 'x'))
        self.assertIsInstance(m, dlb.ex.rundb.FilesystemObjectMemo)

        self.assertEqual(sr0.st_mode, m.stat.mode)
        self.assertEqual(sr0.st_size, m.stat.size)
        self.assertEqual(sr0.st_mtime_ns, m.stat.mtime_ns)
        self.assertEqual(sr0.st_uid, m.stat.uid)
        self.assertEqual(sr0.st_gid, m.stat.gid)
        self.assertIsNone(m.symlink_target)

    def test_return_stat_and_target_for_existing_directory_for_str(self):
        os.mkdir('d')
        os.chmod('d', 0x000)
        try:
            try:
                os.symlink('d' + os.path.sep, 's', target_is_directory=True)
                # note: trailing os.path.sep is necessary irrespective of target_is_directory
            except OSError:  # on platform or filesystem that does not support symlinks
                self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
                raise unittest.SkipTest from None

            sr0 = os.lstat('s')
            m = dlb.ex.worktree.read_filesystem_object_memo(os.path.join(os.getcwd(), 's'))
            self.assertIsInstance(m, dlb.ex.rundb.FilesystemObjectMemo)

            self.assertEqual(sr0.st_mode, m.stat.mode)
            self.assertEqual(m.symlink_target, 'd' + os.path.sep)
        finally:
            os.chmod('d', 0x777)

    def test_return_stat_and_target_for_existing_directory_for_path(self):
        os.mkdir('d')
        os.chmod('d', 0x000)
        try:
            try:
                os.symlink('d' + os.path.sep, 's', target_is_directory=True)
                # note: trailing os.path.sep is necessary irrespective of target_is_directory
            except OSError:  # on platform or filesystem that does not support symlinks
                self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
                raise unittest.SkipTest from None

            sr0 = os.lstat('s')
            m = dlb.ex.worktree.read_filesystem_object_memo(dlb.fs.Path(os.path.join(os.getcwd(), 's')))
            self.assertIsInstance(m, dlb.ex.rundb.FilesystemObjectMemo)

            self.assertEqual(sr0.st_mode, m.stat.mode)
            self.assertIsInstance(m.symlink_target, str)
            self.assertEqual(m.symlink_target, 'd' + os.path.sep)
        finally:
            os.chmod('d', 0x777)


class NormalizeDotDotWithoutReference(unittest.TestCase):

    def test_is_correct(self):
        c = dlb.ex.worktree.normalize_dotdot_native_components(('a', 'b', 'c'))
        self.assertEqual(('a', 'b', 'c'), c)

        c = dlb.ex.worktree.normalize_dotdot_native_components(('a', '..', 'b', 'c', '..'))
        self.assertEqual(('b',), c)

        c = dlb.ex.worktree.normalize_dotdot_native_components(('a', 'b', '..', '..'))
        self.assertEqual((), c)

        c = dlb.ex.worktree.normalize_dotdot_native_components(('a', 'b', '..', '..', 'a'))
        self.assertEqual(('a',), c)

    def test_fails_for_upwards_path(self):
        with self.assertRaises(dlb.ex.worktree.WorkingTreePathError) as cm:
            dlb.ex.worktree.normalize_dotdot_native_components(('..',))
        self.assertEqual("is an upwards path: '../'", str(cm.exception))

        with self.assertRaises(dlb.ex.worktree.WorkingTreePathError) as cm:
            dlb.ex.worktree.normalize_dotdot_native_components(('a', '..', '..', 'b', 'a', 'b'))
        self.assertEqual("is an upwards path: 'a/../../b/a/b'", str(cm.exception))

        with self.assertRaises(dlb.ex.worktree.WorkingTreePathError) as cm:
            dlb.ex.worktree.normalize_dotdot_native_components(('tmp', '..', '..'))
        self.assertEqual("is an upwards path: 'tmp/../../'", str(cm.exception))


class NormalizeDotDotWithReference(tools_for_test.TemporaryDirectoryTestCase):

    def test_without_symlink_is_correct(self):
        os.makedirs('a')
        os.makedirs(os.path.join('c', 'd', 'e'))
        c = dlb.ex.worktree.normalize_dotdot_native_components(('a', '..', 'c', 'd', 'e', '..'), ref_dir_path=os.getcwd())
        self.assertEqual(('c', 'd'), c)

        c = dlb.ex.worktree.normalize_dotdot_native_components(('a', 'b'), ref_dir_path='/tmp')
        self.assertEqual(('a', 'b'), c)

    def test_with_nonparent_symlink_is_correct(self):
        os.makedirs('a')
        os.makedirs(os.path.join('x', 'd', 'e'))

        try:
            os.symlink('x', 'c', target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        c = dlb.ex.worktree.normalize_dotdot_native_components(('a', '..', 'c', 'd', 'e', '..'), ref_dir_path=os.getcwd())
        self.assertEqual(('c', 'd'), c)

    def test_fails_for_relative_ref_dir(self):
        with self.assertRaises(ValueError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.worktree.normalize_dotdot_native_components(('a', 'b'), ref_dir_path='.')
        self.assertEqual("'ref_dir_path' must be None or absolute", str(cm.exception))

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.worktree.normalize_dotdot_native_components(('a', 'b'), ref_dir_path=b'/tmp')
        self.assertEqual("'ref_dir_path' must be a str", str(cm.exception))

    def test_fails_for_nonexistent_symlink(self):
        os.makedirs('a')
        os.makedirs(os.path.join('c', 'd'))
        with self.assertRaises(dlb.ex.worktree.WorkingTreePathError) as cm:
            dlb.ex.worktree.normalize_dotdot_native_components(('a', '..', 'c', 'd', 'e', '..'), ref_dir_path=os.getcwd())
        self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

    def test_fails_for_parent_symlink(self):
        os.makedirs('x')
        os.makedirs(os.path.join('c', 'd'))

        try:
            os.symlink('x', 'a', target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        regex = r"\A()not a collapsable path, since this is a symbolic link: '.+'\Z"
        with self.assertRaisesRegex(dlb.ex.worktree.WorkingTreePathError, regex):
            dlb.ex.worktree.normalize_dotdot_native_components(('a', '..', 'c', 'd', 'e', '..'), ref_dir_path=os.getcwd())
