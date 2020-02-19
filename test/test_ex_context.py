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
import dlb.ex
import dlb.ex.rundb
import pathlib
import stat
import time
import unittest
import tools_for_test


class ImportTest(unittest.TestCase):

    def test_all_is_correct(self):
        import dlb.ex.context
        self.assertEqual({
            'Context',
            'ContextNestingError',
            'NotRunningError',
            'ManagementTreeError',
            'NoWorkingTreeError',
            'WorkingTreeTimeError',
            'NonActiveContextAccessError'},
            set(dlb.ex.context.__all__))
        self.assertTrue('Context' in dir(dlb.ex))

    def test_attributes_of_contextmeta_and_rootsspecifics_to_not_clash(self):
        rs = set(n for n in dlb.ex.context._RootSpecifics.__dict__ if not n.startswith('_'))
        mc = set(n for n in dlb.ex.context._ContextMeta.__dict__ if not n.startswith('_'))
        self.assertEqual(set(), rs.intersection(mc))


# noinspection PyPropertyAccess
class AccessTest(unittest.TestCase):

    def test_public_attribute_are_readonly(self):
        with self.assertRaises(AttributeError):
            dlb.ex.Context.active = None
        with self.assertRaises(AttributeError):
            dlb.ex.Context.root = None

        with self.assertRaises(AttributeError) as cm:
            dlb.ex.Context.xyz = 1
        self.assertEqual("public attributes of 'dlb.ex.Context' are read-only", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            dlb.ex.Context().xyz = 1
        self.assertEqual("public attributes of 'dlb.ex.Context' instances are read-only", str(cm.exception))


class NestingTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_if_not_running(self):
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.active

    def test_can_by_nested(self):
        pathlib.Path('.dlbroot').mkdir()
        with dlb.ex.Context() as c1:
            self.assertIs(dlb.ex.Context.active, c1)
            self.assertIs(c1.active, c1)

            with dlb.ex.Context() as c2:
                self.assertIs(dlb.ex.Context.active, c2)
                self.assertIs(c1.active, c2)

            self.assertIs(dlb.ex.Context.active, c1)

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.active

    def test_nesting_error_is_detected(self):
        pathlib.Path('.dlbroot').mkdir()
        with dlb.ex.Context():
            with self.assertRaises(dlb.ex.context.ContextNestingError):
                with dlb.ex.Context():
                    dlb.ex.context._contexts.pop()

    def test_meaningful_exception_on_attribute_error(self):
        pathlib.Path('.dlbroot').mkdir()

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.non_existing_attribute

        with dlb.ex.Context() as c:
            with self.assertRaises(AttributeError) as cm:
                dlb.ex.Context._non_existing_attribute
            self.assertEqual(str(cm.exception), "type object 'Context' has no attribute '_non_existing_attribute'")

            with self.assertRaises(AttributeError) as cm:
                c._non_existing_attribute
            self.assertEqual(str(cm.exception), "'Context' object has no attribute '_non_existing_attribute'")

            msg = "'Context' object has no attribute 'non_existing_attribute'"

            with self.assertRaises(AttributeError) as cm:
                dlb.ex.Context.non_existing_attribute
            self.assertEqual(str(cm.exception), msg)

            with self.assertRaises(AttributeError) as cm:
                c.non_existing_attribute
            self.assertEqual(str(cm.exception), msg)


class ReuseTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_context_can_be_reused(self):
        pathlib.Path('.dlbroot').mkdir()
        c = dlb.ex.Context()
        with c:
            pass
        with c:
            pass


class WorkingTreeRequirementTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_management_tree_paths_are_portable(self):
        import dlb.fs
        dlb.fs.PortablePath(dlb.ex.context._MANAGEMENTTREE_DIR_NAME)
        dlb.fs.PortablePath(dlb.ex.context._MTIME_PROBE_FILE_NAME)
        dlb.fs.PortablePath(dlb.ex.context._RUNDB_FILE_NAME)

    def test_fails_if_dlbroot_does_not_exist(self):
        with self.assertRaises(dlb.ex.context.NoWorkingTreeError) as cm:
            with dlb.ex.Context():
                pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))

    def test_fails_if_dlbroot_is_file(self):
        with open('.dlbroot', 'wb'):
            pass

        with self.assertRaises(dlb.ex.context.NoWorkingTreeError) as cm:
            with dlb.ex.Context():
                pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))

    def test_fails_if_dlbroot_is_symlink_to_dir(self):
        pathlib.Path('dlbroot_sysmlink_target').mkdir()

        try:
            pathlib.Path('.dlbroot').symlink_to('dlbroot_sysmlink_target', target_is_directory=True)
            self.assertTrue(pathlib.Path('.dlbroot').is_symlink())
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with self.assertRaises(dlb.ex.context.NoWorkingTreeError) as cm:
            with dlb.ex.Context():
                pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))


class ManagementTreeSetupTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_missing_filesystem_objects_are_created(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()
        with dlb.ex.Context():
            self.assertTrue((wdr / 'o').is_file())
            self.assertTrue((wdr / 't').is_dir())

    def test_temp_dir_is_recreated_if_nonempty_directory(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()
        wdr_t = wdr / 't'
        wdr_t.mkdir()
        (wdr_t / 'c').mkdir()

        with (wdr_t / 'a').open('wb'):
            pass
        with (wdr_t / 'c' / 'b').open('wb'):
            pass

        sr0 = wdr_t.stat()
        wdr_t.chmod(stat.S_IMODE(sr0.st_mode) ^ stat.S_IXOTH)  # change permission
        sr1 = wdr_t.stat()
        if stat.S_IMODE(sr0.st_mode) == stat.S_IMODE(sr1.st_mode):
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, the permission should have changed')

        with dlb.ex.Context():
            self.assertTrue(wdr_t.is_dir())
            self.assertTupleEqual((), tuple(p for p in wdr_t.iterdir()))
            sr2 = wdr_t.stat()
            self.assertNotEqual(sr1, sr2)  # since inode could be reused, comparison of inodes would not work reliably

    def test_temp_dir_is_recreated_if_symlink(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()
        wdr_t = wdr / 't'

        symlink_target = wdr / 't_sysmlink_target'
        symlink_target.mkdir()
        try:
            wdr_t.symlink_to(symlink_target, target_is_directory=True)
            self.assertTrue(wdr_t.is_symlink())
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            self.assertTrue(wdr_t.is_dir())
            self.assertFalse(wdr_t.is_symlink())

    def test_mtime_probe_file_is_recreated_if_directory(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()
        wdr_o = (wdr / 'o')
        wdr_o.mkdir()
        (wdr_o / 'c').mkdir()

        with (wdr_o / 'a').open('wb'):
            pass
        with (wdr_o / 'c' / 'b').open('wb'):
            pass

        with dlb.ex.Context():
            self.assertTrue(wdr_o.is_file())

    def test_mtime_probe_uppercase_file_is_removed(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()

        with (wdr / 'o').open('xb'):
            pass
        try:
            with (wdr / 'O').open('xb'):
                pass
        except FileExistsError:
            raise unittest.SkipTest from None  # filesystem is not case-sensitive

        with dlb.ex.Context():
            self.assertTrue((wdr / 'o').is_file())
            self.assertFalse((wdr / 'O').exists())

    def test_meaningful_exception_on_permission_error_while_setup(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()
        wdr_t = wdr / 't'
        wdr_t.mkdir()
        (wdr_t / 'c').mkdir()
        wdr_t.chmod(0o000)

        regex = (
            r"(?m)\A"
            r"failed to setup management tree for '.*'\n"
            r"  \| reason: .*'.+[/\\]+\.dlbroot[/\\]+t'.*\Z"
        )
        with self.assertRaisesRegex(dlb.ex.context.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass

        wdr_t.chmod(0o777)

    def test_meaningful_exception_on_permission_error_while_cleanup(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()
        wdr_t = wdr / 't'

        regex = (
            r"(?m)\A"
            r"failed to cleanup management tree for '.*'\n"
            r"  \| reason: .*'.+[/\\]+\.dlbroot[/\\]+.*'.*\Z"
        )
        with self.assertRaisesRegex(dlb.ex.context.ManagementTreeError, regex):
            with dlb.ex.Context():
                (wdr_t / 'c').mkdir()
                wdr_t.chmod(0o000)
        wdr_t.chmod(0o777)


class PathsTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_root_is_unavailable_if_not_running(self):
        pathlib.Path('.dlbroot').mkdir()

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.root_path

        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex.context.NotRunningError):
            c.root_path

    def test_root_is_correct(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context() as c:
            self.assertIsInstance(c.root_path, dlb.fs.Path)
            self.assertEqual(str(pathlib.Path.cwd().absolute()), str(c.root_path.native))
            cl = dlb.ex.Context.root_path
            self.assertEqual(c.root_path, cl)

    def test_path_class_is_correct(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            self.assertEqual(dlb.ex.Context.path_cls, dlb.fs.NoSpacePath)
            self.assertEqual(dlb.ex.Context.root_path.__class__, dlb.fs.NoSpacePath)
            with dlb.ex.Context(path_cls=dlb.fs.Path) as c:
                self.assertEqual(c.path_cls, dlb.fs.Path)
                self.assertEqual(dlb.ex.Context.path_cls, dlb.fs.Path)  # refers to active context
                self.assertEqual(dlb.ex.Context.root_path.__class__, dlb.fs.NoSpacePath)

    def test_entering_fails_if_path_not_representable(self):
        pathlib.Path('x y').mkdir()

        with tools_for_test.DirectoryChanger('x y'):
            pathlib.Path('.dlbroot').mkdir()

            regex = (
                r"(?m)\A"
                r"current directory violates imposed path restrictions\n"
                r"  \| reason: .*NoSpacePath.*'.+'.*\n"
                r"  \| move the working directory or choose a less restrictive path class for the root context\Z"
            )
            with self.assertRaisesRegex(ValueError, regex):
                with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
                    pass

            with dlb.ex.Context():  # no exception
                regex = (
                    r"(?m)\A"
                    r"working tree's root path violates path restrictions imposed by this context\n"
                    r"  \| reason: .*NoSpacePath.*'.+'.*\n"
                    r"  \| move the working directory or choose a less restrictive path class for the root context\Z"
                )
                with self.assertRaisesRegex(ValueError, regex):
                    with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
                        pass


class WorkingTreeTimeTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_time_is_unavailable_if_not_running(self):
        pathlib.Path('.dlbroot').mkdir()
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.working_tree_time_ns

    def test_time_does_change_after_at_most_15secs(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context():
            start_time = time.time_ns()
            start_working_tree_time = dlb.ex.Context.working_tree_time_ns

            while dlb.ex.Context.working_tree_time_ns == start_working_tree_time:
                self.assertLessEqual((time.time_ns() - start_time) / 1e9, 15.0)
                time.sleep(0.015)  # typical effective working tree time resolution: 10 ms

    def test_exit_does_delay_to_next_change(self):
        pathlib.Path('.dlbroot').mkdir()

        for i in range(10):  # might also pass by chance (transition of working tree time too close at exit context)
            with dlb.ex.Context():
                enter_time = dlb.ex.Context.working_tree_time_ns
            with dlb.ex.Context():
                exit_time = dlb.ex.Context.working_tree_time_ns
            self.assertNotEqual(enter_time, exit_time)


class RunDatabaseTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_nonexisting_is_created(self):
        pathlib.Path('.dlbroot').mkdir()
        with dlb.ex.Context():
            self.assertTrue((pathlib.Path('.dlbroot') / 'runs.sqlite').is_file())

    def test_access_is_possible_in_nonobvious_way_when_running(self):
        pathlib.Path('.dlbroot').mkdir()
        with dlb.ex.Context():
            self.assertIsInstance(dlb.ex.context._get_rundb(), dlb.ex.rundb.Database)

    def test_access_not_possible_in_nobvious_way(self):
        pathlib.Path('.dlbroot').mkdir()
        with dlb.ex.Context():
            with self.assertRaises(AttributeError):
                dlb.ex.Context.run_db_()

    def test_access_fails_if_not_running(self):
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.context._get_rundb()


class ProcessLockTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fail_if_lock_dir_exists(self):
        pathlib.Path('.dlbroot').mkdir()
        (pathlib.Path('.dlbroot') / 'lock').mkdir()

        regex = (
            r"(?m)\A"
            r"cannot acquire lock for exclusive access to working tree '.*'\n"
            r"  \| reason: .*'.+[/\\]+\.dlbroot[/\\]+lock'.*\n"
            r"  \| to break the lock \(if you are sure no other dlb process is running\): "
            r"remove '.*[/\\]+\.dlbroot[/\\]+lock'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.context.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass

    def test_meaningful_exception_on_permission_error(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()
        wdr.chmod(0o000)

        regex = (
            r"(?m)\A"
            r"cannot acquire lock for exclusive access to working tree '.*'\n"
            r"  \| reason: .*'.+[/\\]+\.dlbroot[/\\]+lock'.*\n"
            r"  \| to break the lock \(if you are sure no other dlb process is running\): "
            r"remove '.*[/\\]+\.dlbroot[/\\]+lock'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.context.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass

        wdr.chmod(0o777)


class TemporaryFilesystemObjectsTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_creates_regular_file(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()

        with dlb.ex.Context():
            t = dlb.ex.Context.root_path / '.dlbroot/t'

            p = dlb.ex.Context.create_temporary()
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertFalse(p.is_dir())
            self.assertTrue(p.native.raw.is_file())
            self.assertEqual(t.native.raw, p.native.raw.parent)

            p = dlb.ex.Context.create_temporary(is_dir=False, suffix='.o', prefix='aha')
            self.assertTrue(p.native.raw.is_file())
            self.assertEqual(t.native.raw, p.native.raw.parent)
            self.assertTrue(p.parts[-1].startswith('aha'), repr(p))
            self.assertTrue(p.parts[-1].endswith('.o'), repr(p))

        self.assertFalse((wdr / 't').exists())

    def test_creates_directory(self):
        wdr = pathlib.Path('.dlbroot')
        wdr.mkdir()

        with dlb.ex.Context():
            t = dlb.ex.Context.root_path / '.dlbroot/t'
            p = dlb.ex.Context.create_temporary(is_dir=True)
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(p.is_dir())
            self.assertTrue(p.native.raw.is_dir())
            self.assertEqual(t.native.raw, p.native.raw.parent)

            p = dlb.ex.Context.create_temporary(is_dir=True, suffix='.o', prefix='aha')
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(p.native.raw.is_dir())
            self.assertEqual(t.native.raw, p.native.raw.parent)
            self.assertTrue(p.parts[-1].startswith('aha'), repr(p))
            self.assertTrue(p.parts[-1].endswith('.o'), repr(p))

        self.assertFalse((wdr / 't').exists())

    def test_fails_for_if_not_running(self):
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.create_temporary()
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.create_temporary(is_dir=True)

    def test_fails_for_bytes_prefix_or_suffix(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context():
            with self.assertRaises(TypeError):
                dlb.ex.Context.create_temporary(prefix=b'x')
            with self.assertRaises(TypeError):
                dlb.ex.Context.create_temporary(suffix=b'y')

    def test_fails_for_empty_prefix(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context():
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(prefix='')
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(is_dir=True, prefix='')

    def test_fails_for_path_separator_in_prefix(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context():
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(prefix='x' + os.path.sep)
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(is_dir=True, prefix='x' + os.path.sep + '..' + os.path.sep)

    def test_fails_if_path_not_representable(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            regex = (
                r"(?m)\A"
                r"path violates imposed path restrictions\n"
                r"  \| reason: .*NoSpacePath.*'.+'.*\n"
                r"  \| check specified 'prefix' and 'suffix'\Z"
            )
            with self.assertRaisesRegex(ValueError, regex):
                dlb.ex.Context.create_temporary(suffix='x y')


class ManagedTreePathTest(tools_for_test.TemporaryDirectoryTestCase):

    class StupidPath(dlb.fs.Path):
        def check_restriction_to_base(self):
            if self.parts[:1] == ('b',):
                raise ValueError('hehe')

    # noinspection PyCallingNonCallable,PyArgumentList
    def test_root_is_managed_tree_path(self):
        pathlib.Path('.dlbroot').mkdir()
        pathlib.Path('a').mkdir()
        (pathlib.Path('a') / 'b').mkdir()
        with (pathlib.Path('a') / 'b' / 'c').open('w'):
            pass

        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            # noinspection PyPep8Naming
            C = dlb.ex.Context.path_cls
            p = dlb.ex.Context.managed_tree_path_of(dlb.ex.Context.root_path)
            self.assertIs(p.__class__, C)
            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, C('.', is_dir=True))

            p = dlb.ex.Context.managed_tree_path_of(dlb.ex.Context.root_path.native.raw / 'a' / 'b')
            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, C('a/b', is_dir=True))

            p = dlb.ex.Context.managed_tree_path_of(dlb.ex.Context.root_path.native.raw / 'a' / 'b' / 'c')
            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, C('a/b/c', is_dir=False))

    def test_absolute_path_in_working_tree_is_correct(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context():
            (pathlib.Path('a') / 'b' / 'c').mkdir(parents=True)

            p = dlb.ex.Context.managed_tree_path_of(pathlib.Path.cwd())
            self.assertEqual(dlb.fs.Path('.'), p)

            p = dlb.ex.Context.managed_tree_path_of(pathlib.Path.cwd() / 'a' / 'b' / 'c' / '..')
            self.assertEqual(dlb.fs.Path('a/b/'), p)

    def test_fail_for_absolute_path_outside_working_tree(self):
        (pathlib.Path('a') / 'b' / 'c').mkdir(parents=True)
        (pathlib.Path('a') / 'b2' / 'c2').mkdir(parents=True)

        old_cw = pathlib.Path.cwd()

        with tools_for_test.DirectoryChanger(pathlib.Path('a') / 'b'):
            pathlib.Path('.dlbroot').mkdir()
            with dlb.ex.Context():
                with self.assertRaises(dlb.fs.manip.PathNormalizationError) as cm:
                    dlb.ex.Context.managed_tree_path_of(old_cw / 'a' / 'b2' / 'c2')
                msg = "does not start with the working tree's root path"
                self.assertEqual(msg, str(cm.exception))

    def test_fails_on_nonrepresentable(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            regexp = r"\A()invalid path for 'NoSpacePath': .+\Z"
            with self.assertRaisesRegex(ValueError, regexp):
                dlb.ex.Context.managed_tree_path_of('a /b', existing=True, collapsable=True)

        with dlb.ex.Context(path_cls=ManagedTreePathTest.StupidPath):
            regexp = r"\A()invalid path for 'ManagedTreePathTest\.StupidPath': .+\Z"
            with self.assertRaisesRegex(ValueError, regexp):
                dlb.ex.Context.managed_tree_path_of(dlb.fs.Path('a/../b'), existing=True, collapsable=True)

    def test_fails_on_upwards(self):
        pathlib.Path('.dlbroot').mkdir()
        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            regexp = r"\A()is an upwards path: .+\Z"
            with self.assertRaisesRegex(dlb.fs.manip.PathNormalizationError, regexp):
                dlb.ex.Context.managed_tree_path_of(dlb.fs.Path('a/../..'), existing=True, collapsable=True)

    def test_succeeds_on_nonexisting_if_assuming(self):
        pathlib.Path('.dlbroot').mkdir()
        with dlb.ex.Context():
            dlb.ex.Context.managed_tree_path_of('a/b', existing=True)

    def test_fails_on_nonexisting_if_not_assuming(self):
        pathlib.Path('.dlbroot').mkdir()
        with dlb.ex.Context():
            with self.assertRaises(dlb.fs.manip.PathNormalizationError) as cm:
                dlb.ex.Context.managed_tree_path_of('a/b')
            self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

            with self.assertRaises(dlb.fs.manip.PathNormalizationError) as cm:
                dlb.ex.Context.managed_tree_path_of('a/..')
            self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

    def test_fails_on_symlink_in_managedtree_if_not_assuming(self):
        pathlib.Path('.dlbroot').mkdir()
        (pathlib.Path('x') / 'b').mkdir(parents=True)

        try:
            pathlib.Path('a').symlink_to('x', target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            with self.assertRaises(dlb.fs.manip.PathNormalizationError) as cm:
                dlb.ex.Context.managed_tree_path_of('a/../b', collapsable=True)
            self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

    def test_fails_on_parent(self):
        pathlib.Path('u').mkdir()
        with tools_for_test.DirectoryChanger('u'):
            pathlib.Path('.dlbroot').mkdir()
            with dlb.ex.Context():
                with self.assertRaises(ValueError):
                    dlb.ex.Context.managed_tree_path_of('../')

    def test_fails_on_management_tree(self):
        pathlib.Path('.dlbroot').mkdir()
        (pathlib.Path('.dlbroot') / 'u').mkdir()

        with dlb.ex.Context():
            with self.assertRaises(ValueError):
                dlb.ex.Context.managed_tree_path_of('.dlbroot')
            with self.assertRaises(ValueError):
                dlb.ex.Context.managed_tree_path_of('.dlbroot/u')

    # noinspection PyCallingNonCallable,PyTypeChecker
    def test_corrects_isdir_if_notassuming(self):
        pathlib.Path('.dlbroot').mkdir()
        pathlib.Path('d').mkdir()
        with open('f', 'w'):
            pass

        with dlb.ex.Context():
            # noinspection PyPep8Naming
            C = dlb.ex.Context.path_cls
            self.assertEqual(dlb.ex.Context.managed_tree_path_of('d'), C('d/'))
            self.assertEqual(dlb.ex.Context.managed_tree_path_of('f/'), C('f'))

    def test_fail_if_unsupported_type(self):
        pathlib.Path('.dlbroot').mkdir()

        with dlb.ex.Context():
            with self.assertRaises(TypeError) as cm:
                dlb.ex.Context.managed_tree_path_of(3)
            msg = "'path' must be a str or a dlb.fs.Path or pathlib.Path object"
            self.assertEqual(msg, str(cm.exception))


class ReprTest(unittest.TestCase):

    def test_repr_name_reflects_recommended_module(self):
        self.assertEqual(repr(dlb.ex.Context), "<class 'dlb.ex.Context'>")
        self.assertEqual(repr(dlb.ex.context._EnvVarDict), "<class 'dlb.ex.Context.EnvVarDict'>")
