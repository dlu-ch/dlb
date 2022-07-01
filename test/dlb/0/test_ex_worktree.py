# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex._worktree
import os.path
import string
import tempfile
import unittest
import testtool


class FilenamePortabilityTest(unittest.TestCase):

    def test_management_tree_paths_are_portable(self):
        import dlb.fs
        dlb.fs.PortablePath(dlb.ex._worktree.MANAGEMENTTREE_DIR_NAME)
        dlb.fs.PortablePath(dlb.ex._worktree.MTIME_PROBE_FILE_NAME)
        dlb.fs.PortablePath(dlb.ex._worktree.RUNDB_FILE_NAME_TEMPLATE.format('1'))


class RemoveFilesystemObjectTest(testenv.TemporaryDirectoryTestCase):

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
        open('x', 'wb').close()

        with self.assertRaises(ValueError) as cm:
            dlb.ex._worktree.remove_filesystem_object('x')
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex._worktree.remove_filesystem_object(dlb.fs.Path('x'))
        escaped_sep = '\\\\' if os.path.sep == '\\' else '/'
        self.assertEqual("not an absolute path: '.{}x'".format(escaped_sep), str(cm.exception))

        self.assertTrue(os.path.isfile('x'))  # still exists

        with self.assertRaises(ValueError) as cm:
            dlb.ex._worktree.remove_filesystem_object('')
        self.assertEqual("not an absolute path: ''", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex._worktree.remove_filesystem_object(dlb.fs.Path('.'))
        self.assertEqual("not an absolute path: '.'", str(cm.exception))

    # noinspection PyTypeChecker
    def test_fails_for_bytes_path(self):
        open('x', 'wb').close()

        with self.assertRaises(TypeError) as cm:
            dlb.ex._worktree.remove_filesystem_object(b'x')
        self.assertEqual("'abs_path' must be a str or dlb.fs.Path object, not bytes", str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.ex._worktree.remove_filesystem_object('/tmp/x', abs_empty_dir_path=b'x')
        msg = "'abs_empty_dir_path' must be a str or dlb.fs.Path object, not bytes"
        self.assertEqual(msg, str(cm.exception))

    def test_removes_existing_regular_file(self):
        open('f', 'wb').close()

        dlb.ex._worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'f'))

        self.assertFalse(os.path.exists('f'))

    def test_removes_empty_directory(self):
        os.mkdir('d')

        dlb.ex._worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'd'))

        self.assertFalse(os.path.exists('d'))

    def test_removes_symbolic_link(self):
        open('f', 'wb').close()
        testtool.symlink_or_skip('f', 's', target_is_directory=False)

        dlb.ex._worktree.remove_filesystem_object(os.path.join(os.getcwd(), 's'))
        self.assertFalse(os.path.exists('s'))
        self.assertTrue(os.path.exists('f'))  # still exists

    def test_fails_for_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            dlb.ex._worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'n'))

    def test_ignores_for_nonexistent_if_required(self):
        dlb.ex._worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'n'), ignore_non_existent=True)

    def test_fails_for_relative_tmp(self):
        self.create_dir_a_in_cwd()
        with self.assertRaises(ValueError):
            dlb.ex._worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'a'), abs_empty_dir_path='a')

    def test_removes_nonempty_directory_in_place(self):
        self.create_dir_a_in_cwd()
        dlb.ex._worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'a'))
        self.assertFalse(os.path.exists('a'))

    def test_removes_nonempty_directory_in_tmp(self):
        self.create_dir_a_in_cwd()
        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.ex._worktree.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.abspath(abs_temp_dir_path))
        self.assertFalse(os.path.exists('a'))

        self.create_dir_a_in_cwd()
        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.ex._worktree.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=dlb.fs.Path(dlb.fs.Path.Native(os.path.abspath(abs_temp_dir_path))))
        self.assertFalse(os.path.exists('a'))

    def test_fails_for_nonexistent_tmp_if_not_to_ignore(self):
        self.create_dir_a_in_cwd()

        with self.assertRaises(FileNotFoundError):
            dlb.ex._worktree.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.join(os.getcwd(), 'does', 'not', 'exist'))

        dlb.ex._worktree.remove_filesystem_object(
            os.path.join(os.getcwd(), 'a'),
            abs_empty_dir_path=os.path.join(os.getcwd(), 'does', 'not', 'exist'),
            ignore_non_existent=True)

    def test_removes_most_of_nonempty_directory_in_place_if_permission_denied_in_subdirectory(self):
        self.create_dir_a_in_cwd(all_writable=False)

        with self.assertRaises(PermissionError):
            try:
                dlb.ex._worktree.remove_filesystem_object(os.path.join(os.getcwd(), 'a'))
            finally:
                os.chmod(os.path.join('a', 'b1', 'c'), 0o777)

        self.assertTrue(os.path.exists('a'))  # still exists

    def test_removes_nonempty_directory_in_tmp_if_permission_denied_in_subdirectory(self):
        self.create_dir_a_in_cwd(all_writable=False)

        with tempfile.TemporaryDirectory(dir='.') as abs_temp_dir_path:
            dlb.ex._worktree.remove_filesystem_object(
                os.path.join(os.getcwd(), 'a'),
                abs_empty_dir_path=os.path.abspath(abs_temp_dir_path))
            os.chmod(os.path.join(abs_temp_dir_path, 't', 'b1', 'c'), 0o777)

        self.assertFalse(os.path.exists('a'))  # was successful


class ReadFilesystemObjectMemoTest(testenv.TemporaryDirectoryTestCase):

    def test_fails_for_relative_path(self):
        open('x', 'wb').close()

        with self.assertRaises(ValueError) as cm:
            dlb.ex._worktree.read_filesystem_object_memo('x')
        self.assertEqual("not an absolute path: 'x'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex._worktree.read_filesystem_object_memo(dlb.fs.Path('x'))
        escaped_sep = '\\\\' if os.path.sep == '\\' else '/'
        self.assertEqual("not an absolute path: '.{}x'".format(escaped_sep), str(cm.exception))

    def test_fails_for_bytes_path(self):
        open('x', 'wb').close()

        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex._worktree.read_filesystem_object_memo(b'x')
        self.assertEqual("'abs_path' must be a str or path, not bytes", str(cm.exception))

    def test_fails_for_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            dlb.ex._worktree.read_filesystem_object_memo(os.path.join(os.getcwd(), 'x'))

    def test_return_stat_for_existing_regular(self):
        open('x', 'wb').close()

        sr0 = os.lstat('x')

        m = dlb.ex._worktree.read_filesystem_object_memo(os.path.join(os.getcwd(), 'x'))
        self.assertIsInstance(m, dlb.ex._rundb.FilesystemObjectMemo)

        self.assertEqual(sr0.st_mode, m.stat.mode)
        self.assertEqual(sr0.st_size, m.stat.size)
        self.assertEqual(sr0.st_mtime_ns, m.stat.mtime_ns)
        self.assertEqual(sr0.st_uid, m.stat.uid)
        self.assertEqual(sr0.st_gid, m.stat.gid)
        self.assertIsNone(m.symlink_target)

    def test_return_stat_and_target_for_existing_directory_for_str(self):
        os.mkdir('d')
        orig_mode = os.stat('d').st_mode
        os.chmod('d', 0x000)

        try:
            testtool.symlink_or_skip('d' + os.path.sep, 's', target_is_directory=True)
            # note: trailing os.path.sep is necessary irrespective of target_is_directory

            sr0 = os.lstat('s')
            m = dlb.ex._worktree.read_filesystem_object_memo(os.path.join(os.getcwd(), 's'))
            self.assertIsInstance(m, dlb.ex._rundb.FilesystemObjectMemo)

            self.assertEqual(sr0.st_mode, m.stat.mode)
            self.assertEqual(m.symlink_target, 'd' + os.path.sep)
        finally:
            os.chmod('d', orig_mode)  # would raise PermissionError on FreeBSD if more permissive than initially

    def test_return_stat_and_target_for_existing_directory_for_path(self):
        os.mkdir('d')
        orig_mode = os.stat('d').st_mode
        os.chmod('d', 0x000)

        try:
            testtool.symlink_or_skip('d' + os.path.sep, 's', target_is_directory=True)
            # note: trailing os.path.sep is necessary irrespective of target_is_directory

            sr0 = os.lstat('s')
            m = dlb.ex._worktree.read_filesystem_object_memo(dlb.fs.Path(os.path.join(os.getcwd(), 's')))
            self.assertIsInstance(m, dlb.ex._rundb.FilesystemObjectMemo)

            self.assertEqual(sr0.st_mode, m.stat.mode)
            self.assertIsInstance(m.symlink_target, str)
            self.assertEqual(m.symlink_target, 'd' + os.path.sep)
        finally:
            os.chmod('d', orig_mode)  # would raise PermissionError on FreeBSD if more permissive than initially


class NormalizeDotDotWithoutReference(unittest.TestCase):

    def test_is_correct(self):
        c = dlb.ex._worktree.normalize_dotdot_native_components(('a', 'b', 'c'))
        self.assertEqual(('a', 'b', 'c'), c)

        c = dlb.ex._worktree.normalize_dotdot_native_components(('a', '..', 'b', 'c', '..'))
        self.assertEqual(('b',), c)

        c = dlb.ex._worktree.normalize_dotdot_native_components(('a', 'b', '..', '..'))
        self.assertEqual((), c)

        c = dlb.ex._worktree.normalize_dotdot_native_components(('a', 'b', '..', '..', 'a'))
        self.assertEqual(('a',), c)

    def test_fails_for_upwards_path(self):
        with self.assertRaises(dlb.ex._error.WorkingTreePathError) as cm:
            dlb.ex._worktree.normalize_dotdot_native_components(('..',))
        self.assertEqual("is an upwards path: '../'", str(cm.exception))

        with self.assertRaises(dlb.ex._error.WorkingTreePathError) as cm:
            dlb.ex._worktree.normalize_dotdot_native_components(('a', '..', '..', 'b', 'a', 'b'))
        self.assertEqual("is an upwards path: 'a/../../b/a/b'", str(cm.exception))

        with self.assertRaises(dlb.ex._error.WorkingTreePathError) as cm:
            dlb.ex._worktree.normalize_dotdot_native_components(('tmp', '..', '..'))
        self.assertEqual("is an upwards path: 'tmp/../../'", str(cm.exception))


class NormalizeDotDotWithReference(testenv.TemporaryDirectoryTestCase):

    def test_without_symlink_is_correct(self):
        os.makedirs('a')
        os.makedirs(os.path.join('c', 'd', 'e'))
        c = dlb.ex._worktree.normalize_dotdot_native_components(('a', '..', 'c', 'd', 'e', '..'),
                                                                ref_dir_path=os.getcwd())
        self.assertEqual(('c', 'd'), c)

        c = dlb.ex._worktree.normalize_dotdot_native_components(('a', 'b'), ref_dir_path='/tmp')
        self.assertEqual(('a', 'b'), c)

    def test_with_nonparent_symlink_is_correct(self):
        os.makedirs('a')
        os.makedirs(os.path.join('x', 'd', 'e'))
        testtool.symlink_or_skip('x', 'c', target_is_directory=True)

        c = dlb.ex._worktree.normalize_dotdot_native_components(('a', '..', 'c', 'd', 'e', '..'),
                                                                ref_dir_path=os.getcwd())
        self.assertEqual(('c', 'd'), c)

    def test_fails_for_relative_ref_dir(self):
        with self.assertRaises(ValueError) as cm:
            # noinspection PyTypeChecker
            dlb.ex._worktree.normalize_dotdot_native_components(('a', 'b'), ref_dir_path='.')
        self.assertEqual("'ref_dir_path' must be None or absolute", str(cm.exception))

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex._worktree.normalize_dotdot_native_components(('a', 'b'), ref_dir_path=b'/tmp')
        self.assertEqual("'ref_dir_path' must be a str", str(cm.exception))

    def test_fails_for_nonexistent_symlink(self):
        os.makedirs('a')
        os.makedirs(os.path.join('c', 'd'))
        with self.assertRaises(dlb.ex._error.WorkingTreePathError) as cm:
            dlb.ex._worktree.normalize_dotdot_native_components(('a', '..', 'c', 'd', 'e', '..'),
                                                                ref_dir_path=os.getcwd())
        self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

    def test_fails_for_parent_symlink(self):
        os.makedirs('x')
        os.makedirs(os.path.join('c', 'd'))
        testtool.symlink_or_skip('x', 'a', target_is_directory=True)

        regex = r"\A()not a collapsable path, since this is a symbolic link: '.+'\Z"
        with self.assertRaisesRegex(dlb.ex._error.WorkingTreePathError, regex):
            dlb.ex._worktree.normalize_dotdot_native_components(('a', '..', 'c', 'd', 'e', '..'),
                                                                ref_dir_path=os.getcwd())


class GetCheckRootPathFromCwdTest(testenv.TemporaryDirectoryTestCase):

    def test_fails_for_symlink(self):
        os.mkdir('a')
        os.makedirs(os.path.join('x', 'y'))
        testtool.symlink_or_skip(os.path.join('..', 'x'), os.path.join('a', 'b'), target_is_directory=True)

        os.mkdir(os.path.join('a', 'b', 'y', '.dlbroot'))
        with self.assertRaises(dlb.ex._error.NoWorkingTreeError) as cm:
            dlb.ex._worktree.get_checked_root_path_from_cwd(
                os.path.abspath(os.path.join('a', 'b', 'y')), path_cls=dlb.fs.Path)
        msg = (
            "supposedly equivalent forms of current directory's path point to different filesystem objects\n"
            "  | reason: unresolved symbolic links, dlb bug, Python bug or a moved directory\n"
            "  | try again?"
        )
        self.assertEqual(msg, str(cm.exception))


class UniquePathProviderTest(unittest.TestCase):

    def test_generates_prefixed_unique(self):
        pp = dlb.ex._worktree.UniquePathProvider('x/y/')
        self.assertEqual(dlb.fs.Path('x/y/'), pp.root_path)
        self.assertEqual(dlb.fs.Path('x/y/a'), pp.generate())
        self.assertEqual(dlb.fs.Path('x/y/b/'), pp.generate(is_dir=True))
        self.assertEqual(dlb.fs.Path('x/y/c'), pp.generate())

    def test_generated_name_is_valid(self):
        pp = dlb.ex._worktree.UniquePathProvider('.')
        regex = '^[a-z][a-z0-9]*$'
        p = None
        for i in range(26 + 26 * 36 + 26 * 36 * 36):
            p = pp.generate()
            self.assertRegex(p.parts[0], regex)
        self.assertEqual("z99", p.parts[0])

    def test_fails_for_suffix_with_slash(self):
        pp = dlb.ex._worktree.UniquePathProvider('.')
        with self.assertRaises(ValueError) as cm:
            pp.generate(suffix='_/_')
        msg = "'suffix' must not contain '/': '_/_'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_suffix_with_leading_letter(self):
        pp = dlb.ex._worktree.UniquePathProvider('.')
        with self.assertRaises(ValueError) as cm:
            pp.generate(suffix='A')
        msg = "non-empty 'suffix' must start with character from strings.punctuation, not 'A'"
        self.assertEqual(msg, str(cm.exception))


class TemporaryTest(testenv.TemporaryDirectoryTestCase):

    def test_provides_path_with_out_creating(self):
        pp = dlb.ex._worktree.UniquePathProvider('/tmp/does/not/exist/')
        t = dlb.ex._worktree.Temporary(path_provider=pp)
        self.assertIsInstance(t.path, dlb.fs.Path)
        self.assertTrue(t.path.is_absolute())

    def test_fails_for_relative_root_path(self):
        pp = dlb.ex._worktree.UniquePathProvider('.')
        with self.assertRaises(ValueError) as cm:
            dlb.ex._worktree.Temporary(path_provider=pp)
        msg = "'root_path' of 'path_provider' must be absolute"
        self.assertEqual(msg, str(cm.exception))

    def test_contentmanager_creates_and_removes_file(self):
        pp = dlb.ex._worktree.UniquePathProvider(dlb.fs.Path(dlb.fs.Path.Native(os.getcwd()), is_dir=True))
        with dlb.ex._worktree.Temporary(path_provider=pp, is_dir=False) as p:
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(os.path.isfile(p.native))
        self.assertFalse(os.path.exists(p.native))

    def test_contentmanager_creates_and_removes_directory(self):
        pp = dlb.ex._worktree.UniquePathProvider(dlb.fs.Path(dlb.fs.Path.Native(os.getcwd()), is_dir=True))
        with dlb.ex._worktree.Temporary(path_provider=pp, is_dir=True) as p:
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(os.path.isdir(p.native))
            open('f', 'xb').close()
        self.assertFalse(os.path.exists(p.native))

    def test_contentmanager_fails_on_existing_file(self):
        pp = dlb.ex._worktree.UniquePathProvider(dlb.fs.Path(dlb.fs.Path.Native(os.getcwd()), is_dir=True))
        t = dlb.ex._worktree.Temporary(path_provider=pp, is_dir=False)
        open(t.path.native, 'xb').close()
        with self.assertRaises(FileExistsError):
            with t:
                pass
        self.assertTrue(os.path.exists(t.path.native))  # not removed

    def test_contentmanager_fails_on_existing_directory(self):
        pp = dlb.ex._worktree.UniquePathProvider(dlb.fs.Path(dlb.fs.Path.Native(os.getcwd()), is_dir=True))
        t = dlb.ex._worktree.Temporary(path_provider=pp, is_dir=True)
        os.mkdir(t.path.native)
        with self.assertRaises(FileExistsError):
            with t:
                pass
        self.assertTrue(os.path.exists(t.path.native))  # not removed
