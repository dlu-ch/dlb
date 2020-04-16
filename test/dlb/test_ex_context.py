# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import dlb.ex._worktree
import dlb.ex._rundb
import os.path
import stat
import time
import datetime
import unittest


RUNDB_FILENAME = dlb.ex._worktree.rundb_filename_for_schema_version(dlb.ex._rundb.SCHEMA_VERSION)


class AttributeNameTest(unittest.TestCase):

    def test_attributes_of_contextmeta_and_rootsspecifics_to_not_clash(self):
        rs = set(n for n in dlb.ex._context._RootSpecifics.__dict__ if not n.startswith('_'))
        mc = set(n for n in dlb.ex._context._ContextMeta.__dict__ if not n.startswith('_'))
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


class NestingTestNotRunning(unittest.TestCase):

    def test_fails_if_not_running(self):
        with self.assertRaises(dlb.ex._error.NotRunningError):
            dlb.ex.Context.active


class NestingTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_can_by_nested(self):
        with dlb.ex.Context() as c1:
            self.assertIs(dlb.ex.Context.active, c1)
            self.assertIs(c1.active, c1)

            with dlb.ex.Context() as c2:
                self.assertIs(dlb.ex.Context.active, c2)
                self.assertIs(c1.active, c2)

            self.assertIs(dlb.ex.Context.active, c1)

        with self.assertRaises(dlb.ex._error.NotRunningError):
            dlb.ex.Context.active

    def test_nesting_error_is_detected(self):
        with dlb.ex.Context():
            with self.assertRaises(dlb.ex._error.ContextNestingError):
                with dlb.ex.Context():
                    dlb.ex._context._contexts.pop()

    def test_meaningful_exception_on_attribute_error(self):
        with self.assertRaises(dlb.ex._error.NotRunningError):
            dlb.ex.Context.non_existent_attribute

        with dlb.ex.Context() as c:
            with self.assertRaises(AttributeError) as cm:
                dlb.ex.Context._non_existent_attribute
            self.assertEqual(str(cm.exception), "type object 'Context' has no attribute '_non_existent_attribute'")

            with self.assertRaises(AttributeError) as cm:
                c._non_existent_attribute
            self.assertEqual(str(cm.exception), "'Context' object has no attribute '_non_existent_attribute'")

            msg = "'Context' object has no attribute 'non_existent_attribute'"

            with self.assertRaises(AttributeError) as cm:
                dlb.ex.Context.non_existent_attribute
            self.assertEqual(str(cm.exception), msg)

            with self.assertRaises(AttributeError) as cm:
                c.non_existent_attribute
            self.assertEqual(str(cm.exception), msg)


class ReuseTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_context_can_be_reused(self):
        c = dlb.ex.Context()
        with c:
            pass
        with c:
            pass


class WorkingTreeRequirementTest(testenv.TemporaryDirectoryTestCase):

    def test_fails_if_dlbroot_does_not_exist(self):
        with self.assertRaises(dlb.ex._error.NoWorkingTreeError) as cm:
            with dlb.ex.Context():
                pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))

    def test_fails_if_dlbroot_is_file(self):
        open('.dlbroot', 'wb').close()

        with self.assertRaises(dlb.ex._error.NoWorkingTreeError) as cm:
            with dlb.ex.Context():
                pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))

    def test_fails_if_dlbroot_is_symlink_to_dir(self):
        os.mkdir('dlbroot_sysmlink_target')

        try:
            os.symlink('dlbroot_sysmlink_target', '.dlbroot', target_is_directory=True)
            self.assertTrue(os.path.islink('.dlbroot'))
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with self.assertRaises(dlb.ex._error.NoWorkingTreeError) as cm:
            with dlb.ex.Context():
                pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))


class ManagementTreeSetupTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_missing_filesystem_objects_are_created(self):
        with dlb.ex.Context():
            self.assertTrue(os.path.isfile(os.path.join('.dlbroot', 'o')))
            self.assertTrue(os.path.isdir(os.path.join('.dlbroot', 't')))

    def test_temp_dir_is_recreated_if_nonempty_directory(self):
        temp_path = os.path.join('.dlbroot', 't')
        os.makedirs(os.path.join(temp_path, 'c'))

        open(os.path.join(temp_path, 'a'), 'wb').close()
        open(os.path.join(temp_path, 'c', 'b'), 'wb').close()

        sr0 = os.stat(temp_path)
        os.chmod(temp_path, stat.S_IMODE(sr0.st_mode) ^ stat.S_IXOTH)  # change permission
        sr1 = os.stat(temp_path)
        if stat.S_IMODE(sr0.st_mode) == stat.S_IMODE(sr1.st_mode):
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, the permission should have changed')
            raise unittest.SkipTest

        with dlb.ex.Context():
            self.assertTrue(os.path.isdir(temp_path))
            self.assertEqual([], os.listdir(temp_path))
            sr2 = os.stat(temp_path)
            self.assertNotEqual(sr1, sr2)  # since inode could be reused, comparison of inodes would not work reliably

    def test_temp_dir_is_recreated_if_symlink(self):
        temp_path = os.path.join('.dlbroot', 't')

        symlink_target = os.path.join('.dlbroot', 't_sysmlink_target')
        os.mkdir(symlink_target)
        try:
            os.symlink(symlink_target, temp_path, target_is_directory=True)
            self.assertTrue(os.path.islink(temp_path))
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            self.assertTrue(os.path.isdir(temp_path))
            self.assertFalse(os.path.islink(temp_path))

    def test_mtime_probe_file_is_recreated_if_directory(self):
        mprobe_file = os.path.join('.dlbroot', 'o')
        os.mkdir(mprobe_file)
        os.mkdir(os.path.join(mprobe_file, 'c'))

        open(os.path.join(mprobe_file, 'a'), 'wb').close()
        open(os.path.join(mprobe_file, 'c', 'b'), 'wb').close()

        with dlb.ex.Context():
            self.assertTrue(os.path.isfile(mprobe_file))

    def test_mtime_probe_uppercase_file_is_removed(self):
        open(os.path.join('.dlbroot', 'o'), 'xb').close()
        try:
            open(os.path.join('.dlbroot', 'O'), 'xb').close()
        except FileExistsError:
            raise unittest.SkipTest from None  # filesystem is not case-sensitive

        with dlb.ex.Context():
            self.assertTrue(os.path.isfile(os.path.join('.dlbroot', 'o')))
            self.assertFalse(os.path.exists(os.path.join('.dlbroot', 'O')))

    def test_rundb_dir_is_removed(self):
        os.makedirs(os.path.join('.dlbroot', RUNDB_FILENAME))
        with dlb.ex.Context():
            pass
        self.assertTrue(os.path.isfile(os.path.join('.dlbroot', RUNDB_FILENAME)))


class ManagementTreeSetupWithPermissionProblemTest(testenv.TemporaryDirectoryWithChmodTestCase,
                                                   testenv.TemporaryWorkingDirectoryTestCase):

    def test_meaningful_exception(self):
        temp_path = os.path.join('.dlbroot', 't')
        os.mkdir(temp_path)
        open(os.path.join(temp_path, 'f'), 'xb').close()
        os.chmod(temp_path, 0o000)

        regex = (
            r"(?m)\A"
            r"failed to setup management tree for '.*'\n"
            r"  \| reason: .*'.+[\/\]+\.dlbroot[\\/]+t'.*\Z"
        )
        with self.assertRaisesRegex(dlb.ex._error.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass

        os.chmod(temp_path, 0o777)


class ManagementTreeCleanupWithPermissionProblemTest(testenv.TemporaryDirectoryWithChmodTestCase,
                                                     testenv.TemporaryWorkingDirectoryTestCase):

    def test_meaningful_exception(self):
        temp_path = os.path.join('.dlbroot', 't')

        regex = (
            r"(?m)\A"
            r"failed to cleanup management tree for '.*'\n"
            r"  \| reason: .*'.+[/\\]+\.dlbroot[/\\]+.*'.*\Z"
        )
        with self.assertRaisesRegex(dlb.ex._error.ManagementTreeError, regex):
            with dlb.ex.Context():
                os.mkdir(os.path.join(temp_path, 'c'))
                os.chmod(temp_path, 0o000)

        os.chmod(temp_path, 0o777)


class ManagementTreeCleanupTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_meaningful_exception_on_strange_error_while_cleanup(self):
        with self.assertRaises(dlb.ex.ManagementTreeError):
            with dlb.ex.Context() as c:
                c._root_specifics._mtime_probe.close()
                c._root_specifics._mtime_probe = 1

        with self.assertRaises(dlb.ex.ManagementTreeError):
            with dlb.ex.Context() as c:
                c._root_specifics._rundb.close()
                c._root_specifics._rundb = '2'


class RootContextPathTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_root_is_unavailable_if_not_running(self):
        with self.assertRaises(dlb.ex._error.NotRunningError):
            dlb.ex.Context.root_path

        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex._error.NotRunningError):
            c.root_path

    def test_root_is_correct(self):
        with dlb.ex.Context() as c:
            p = c.root_path
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(p.is_absolute())
            self.assertTrue(p.is_dir())
            self.assertEqual(str(os.getcwd()), str(p.native))

            cl = dlb.ex.Context.root_path
            self.assertEqual(p, cl)

    def test_path_class_is_correct(self):
        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            self.assertEqual(dlb.ex.Context.path_cls, dlb.fs.NoSpacePath)
            self.assertEqual(dlb.ex.Context.root_path.__class__, dlb.fs.NoSpacePath)
            with dlb.ex.Context(path_cls=dlb.fs.Path) as c:
                self.assertEqual(c.path_cls, dlb.fs.Path)
                self.assertEqual(dlb.ex.Context.path_cls, dlb.fs.Path)  # refers to active context
                self.assertEqual(dlb.ex.Context.root_path.__class__, dlb.fs.NoSpacePath)


class RootContextInvalidPathTest(testenv.TemporaryDirectoryTestCase):

    def test_fails_for_invalid_path_class(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.Context(path_cls=int)
        self.assertEqual("'path_cls' must be a subclass of 'dlb.fs.Path'", str(cm.exception))

    def test_entering_fails_if_path_not_representable(self):
        os.mkdir('x y')

        with testenv.DirectoryChanger('x y'):
            os.mkdir('.dlbroot')

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


class WorkingTreeTimeTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_time_is_unavailable_if_not_running(self):
        with self.assertRaises(dlb.ex._error.NotRunningError):
            dlb.ex.Context.working_tree_time_ns

    def test_time_does_change_after_at_most_15secs(self):
        with dlb.ex.Context():
            start_time = time.monotonic_ns()
            start_working_tree_time = dlb.ex.Context.working_tree_time_ns

            while dlb.ex.Context.working_tree_time_ns == start_working_tree_time:
                self.assertLessEqual((time.monotonic_ns() - start_time) / 1e9, 15.0)
                time.sleep(0.015)  # typical effective working tree time resolution: 10 ms

    def test_exit_does_delay_to_next_change(self):
        for i in range(10):  # might also pass by chance (transition of working tree time too close to context exit)
            with dlb.ex.Context():
                enter_time = dlb.ex.Context.working_tree_time_ns
            with dlb.ex.Context():
                exit_time = dlb.ex.Context.working_tree_time_ns
            self.assertNotEqual(enter_time, exit_time)

    def test_fails_if_working_tree_time_ns_does_not_change(self):
        r = None
        try:
            regex = (
                r"(?m)\A"
                r"failed to cleanup management tree for '.+'\n"
                r"  \| reason: working tree time did not change for at least 10 s of system time\Z"
            )
            with self.assertRaisesRegex(dlb.ex.ManagementTreeError, regex):
                with dlb.ex.Context() as c:
                    r = c._root_specifics.__class__
                    orig = r.working_tree_time_ns
                    r.working_tree_time_ns = 1
        finally:
            r.working_tree_time_ns = orig


class RunDatabaseNotRunningTest(unittest.TestCase):

    def test_access_fails_if_not_running(self):
        with self.assertRaises(dlb.ex._error.NotRunningError):
            dlb.ex._context._get_rundb()


class RunDatabaseTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_nonexistent_is_created(self):
        with dlb.ex.Context():
            self.assertTrue(os.path.isfile(os.path.join('.dlbroot', RUNDB_FILENAME)))

    def test_access_is_possible_in_nonobvious_way_when_running(self):
        with dlb.ex.Context():
            self.assertIsInstance(dlb.ex._context._get_rundb(), dlb.ex._rundb.Database)

    def test_access_not_possible_in_obvious_way(self):
        with dlb.ex.Context():
            with self.assertRaises(AttributeError):
                dlb.ex.Context.run_db_()

    def test_meaningful_exception_on_corrupt(self):
        with open(os.path.join('.dlbroot', RUNDB_FILENAME), 'xb') as f:
            f.write(b'123')

        with self.assertRaises(dlb.ex.ManagementTreeError) as cm:
            with dlb.ex.Context():
                pass

        self.assertRegex(str(cm.exception), r'\A()could not setup run-database\n')
        self.assertRegex(str(cm.exception), r'\b()sqlite3.DatabaseError\b')
        self.assertRegex(str(cm.exception), r'\b()database corruption\b')


class ProcessLockTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fail_if_lock_dir_exists(self):
        os.mkdir(os.path.join('.dlbroot', 'lock'))

        regex = (
            r"(?m)\A"
            r"cannot acquire lock for exclusive access to working tree '.*'\n"
            r"  \| reason: .*'.+[\\/]+\.dlbroot[\\/]+lock'.*\n"
            r"  \| to break the lock \(if you are sure no other dlb process is running\): "
            r"remove '.*[\\/]+\.dlbroot[\\/]+lock'\Z"
        )
        with self.assertRaisesRegex(dlb.ex._error.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass

    def test_succeeds_if_lock_file_exists(self):
        open(os.path.join('.dlbroot', 'lock'), 'xb').close()
        with dlb.ex.Context():
            pass


class ProcessLockPermissionProblemTest(testenv.TemporaryDirectoryWithChmodTestCase,
                                       testenv.TemporaryWorkingDirectoryTestCase):

    def test_meaningful_exception_on_permission_error(self):
        os.chmod('.dlbroot', 0o000)

        regex = (
            r"(?m)\A"
            r"cannot acquire lock for exclusive access to working tree '.*'\n"
            r"  \| reason: .*'.+[\\/]+\.dlbroot[\\/]+lock'.*\n"
            r"  \| to break the lock \(if you are sure no other dlb process is running\): "
            r"remove '.*[\\/]+\.dlbroot[\\/]+lock'\Z"
        )
        with self.assertRaisesRegex(dlb.ex._error.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass

        os.chmod('.dlbroot', 0o777)

    def test_meaningful_exception_if_unlock_fails(self):
        regex = (
            r"(?m)\A"
            r"failed to cleanup management tree for '.+'\n"
            r"  \| reason: .+\Z"
        )
        with self.assertRaisesRegex(dlb.ex.ManagementTreeError, regex):
            with dlb.ex.Context():
                os.chmod('.dlbroot', 0o000)

        os.chmod('.dlbroot', 0o777)


class TemporaryNotRunningTest(unittest.TestCase):

    def test_fails_for_if_not_running(self):
        with self.assertRaises(dlb.ex._error.NotRunningError):
            dlb.ex.Context.temporary(is_dir=False)
        with self.assertRaises(dlb.ex._error.NotRunningError):
            dlb.ex.Context.temporary(is_dir=True)


class TemporaryTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_creates_regular_file(self):
        with dlb.ex.Context():
            t = dlb.ex.Context.root_path / '.dlbroot/t'

            with dlb.ex.Context.temporary() as p:
                self.assertIsInstance(p, dlb.fs.Path)
                self.assertFalse(p.is_dir())
                self.assertTrue(p.native.raw.is_file())
                self.assertEqual(t.native.raw, p.native.raw.parent)

            with dlb.ex.Context.temporary(is_dir=False, suffix='.o') as p:
                self.assertTrue(p.native.raw.is_file())
                self.assertEqual(t.native.raw, p.native.raw.parent)
                self.assertTrue(p.parts[-1].endswith('.o'), repr(p))

        self.assertFalse(os.path.exists(os.path.join('.dlbroot', 't')))

    def test_creates_directory(self):
        with dlb.ex.Context():
            t = dlb.ex.Context.root_path / '.dlbroot/t'

            with dlb.ex.Context.temporary(is_dir=True) as p:
                self.assertIsInstance(p, dlb.fs.Path)
                self.assertTrue(p.is_dir())
                self.assertTrue(p.native.raw.is_dir())
                self.assertEqual(t.native.raw, p.native.raw.parent)

            with dlb.ex.Context.temporary(is_dir=True, suffix='.o') as p:
                self.assertIsInstance(p, dlb.fs.Path)
                self.assertTrue(p.native.raw.is_dir())
                self.assertEqual(t.native.raw, p.native.raw.parent)
                self.assertTrue(p.parts[-1].endswith('.o'), repr(p))

        self.assertFalse(os.path.exists(os.path.join('.dlbroot', 't')))

    def test_fails_for_slash_in_suffix(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.temporary(suffix='./y')
            msg = "'suffix' must not contain '/': './y'"
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_if_suffix_does_not_starts_with_punctuation(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.temporary(suffix='x')
            msg = "non-empty 'suffix' must start with character from strings.punctuation, not 'x'"
            self.assertEqual(msg, str(cm.exception))


# noinspection PyTypeChecker
class ManagedTreePathTest(testenv.TemporaryWorkingDirectoryTestCase):

    class StupidPath(dlb.fs.Path):
        # noinspection PyUnusedLocal
        def check_restriction_to_base(self, components_checked: bool):
            if self.parts[:1] == ('b',):
                raise ValueError('hehe')

    # noinspection PyCallingNonCallable,PyArgumentList
    def test_root_is_managed_tree_path(self):
        os.makedirs(os.path.join('a', 'b'))
        open(os.path.join('a', 'b', 'c'), 'w').close()

        # noinspection PyTypeChecker
        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            cls = dlb.ex.Context.path_cls
            p = dlb.ex.Context.working_tree_path_of(dlb.ex.Context.root_path)
            self.assertIs(p.__class__, cls)
            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, cls('.', is_dir=True))

            p = dlb.ex.Context.working_tree_path_of(dlb.ex.Context.root_path / dlb.fs.Path('a/b'))
            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, cls('a/b', is_dir=True))

            p = dlb.ex.Context.working_tree_path_of((dlb.ex.Context.root_path / dlb.fs.Path('a/b/c')).native.raw)
            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, cls('a/b/c', is_dir=False))

    def test_absolute_path_in_working_tree_is_correct(self):
        os.makedirs(os.path.join('a', 'b', 'c'))

        with dlb.ex.Context():
            p = dlb.ex.Context.working_tree_path_of(dlb.fs.Path.Native(os.getcwd()), is_dir=True)
            self.assertEqual(dlb.fs.Path('.'), p)

            p = dlb.ex.Context.working_tree_path_of(
                dlb.fs.Path.Native(os.path.join(os.getcwd(), 'a',  'b',  'c',  '..')))
            self.assertEqual(dlb.fs.Path('a/b/'), p)

    def test_is_class_of_argument(self):
        with dlb.ex.Context():
            p = dlb.ex.Context.working_tree_path_of(dlb.fs.NoSpacePath('a/../b'), existing=True, collapsable=True)
            self.assertIs(p.__class__, dlb.fs.NoSpacePath)

    def test_fails_on_nonrepresentable(self):
        with dlb.ex.Context():
            regexp = r"\A()invalid path for 'ManagedTreePathTest\.StupidPath': .+\Z"
            with self.assertRaisesRegex(ValueError, regexp):
                dlb.ex.Context.working_tree_path_of(ManagedTreePathTest.StupidPath('a/../b'),
                                                    existing=True, collapsable=True)

    def test_fails_on_upwards(self):
        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            regexp = r"\A()is an upwards path: .+\Z"
            with self.assertRaisesRegex(dlb.ex.WorkingTreePathError, regexp):
                dlb.ex.Context.working_tree_path_of(dlb.fs.Path('a/../..'), existing=True, collapsable=True)

    def test_succeeds_on_nonexistent_if_assuming(self):
        with dlb.ex.Context():
            dlb.ex.Context.working_tree_path_of('a/b', existing=True)

    def test_fails_on_nonexistent_if_not_assuming(self):
        with dlb.ex.Context():
            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                dlb.ex.Context.working_tree_path_of('a/b')
            self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                dlb.ex.Context.working_tree_path_of('a/..')
            self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

    def test_fails_on_symlink_in_managedtree_if_not_assuming(self):
        os.makedirs(os.path.join('x', 'b'))

        try:
            os.symlink('x', 'a', target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                dlb.ex.Context.working_tree_path_of('a/../b', collapsable=True)
            self.assertIsInstance(cm.exception.oserror, FileNotFoundError)

    def test_fails_on_management_tree_if_not_permitted(self):
        with dlb.ex.Context():
            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                dlb.ex.Context.working_tree_path_of('.dlbroot')
            self.assertEqual("path in non-permitted part of the working tree: '.dlbroot'", str(cm.exception))
            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                dlb.ex.Context.working_tree_path_of('.dlbroot/o')
            self.assertEqual("path in non-permitted part of the working tree: '.dlbroot/o'", str(cm.exception))
            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                dlb.ex.Context.working_tree_path_of('.dlbroot/t')
            self.assertEqual("path in non-permitted part of the working tree: '.dlbroot/t'", str(cm.exception))

            p = dlb.ex.Context.working_tree_path_of('.dlbroot/o', allow_nontemporary_management=True)
            self.assertEqual(dlb.fs.Path('.dlbroot/o'), p)

            with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                dlb.ex.Context.working_tree_path_of('.dlbroot/t', allow_nontemporary_management=True)
            self.assertEqual("path in non-permitted part of the working tree: '.dlbroot/t'", str(cm.exception))

            p = dlb.ex.Context.working_tree_path_of('.dlbroot/t', allow_temporary=True)
            self.assertEqual(dlb.fs.Path('.dlbroot/t/'), p)

    # noinspection PyCallingNonCallable,PyTypeChecker
    def test_corrects_isdir_if_notassuming(self):
        os.mkdir('d')
        open('f', 'w').close()

        with dlb.ex.Context():
            cls = dlb.ex.Context.path_cls
            self.assertEqual(dlb.ex.Context.working_tree_path_of('d'), cls('d/'))
            self.assertEqual(dlb.ex.Context.working_tree_path_of('f/'), cls('f'))

    def test_fail_if_unsupported_type(self):
        with dlb.ex.Context():
            with self.assertRaises(TypeError) as cm:
                dlb.ex.Context.working_tree_path_of(3)
            msg = "'path' must be a str, dlb.fs.Path or pathlib.PurePath object or a sequence, not <class 'int'>"
            self.assertEqual(msg, str(cm.exception))

    def test_isdir_is_respected(self):
        with dlb.ex.Context():
            self.assertTrue(dlb.ex.Context.working_tree_path_of('a', is_dir=True, existing=True).is_dir())
            self.assertFalse(dlb.ex.Context.working_tree_path_of('a', is_dir=False, existing=True).is_dir())
            self.assertFalse(dlb.ex.Context.working_tree_path_of(dlb.fs.Path('a/'),
                                                                 is_dir=False, existing=True).is_dir())


class ManagedTreePathOutsideTest(testenv.TemporaryDirectoryTestCase):

    def test_fails_for_absolute_path_outside_working_tree(self):
        os.makedirs(os.path.join('a', 'b', 'c'))
        os.makedirs(os.path.join('a', 'b2', 'c2'))

        old_cw = os.getcwd()

        with testenv.DirectoryChanger(os.path.join('a', 'b')):
            os.mkdir('.dlbroot')
            with dlb.ex.Context():
                with self.assertRaises(dlb.ex.WorkingTreePathError) as cm:
                    dlb.ex.Context.working_tree_path_of(dlb.fs.Path.Native(os.path.join(old_cw, 'a', 'b2', 'c2')))
                msg = "does not start with the working tree's root path"
                self.assertEqual(msg, str(cm.exception))

    def test_fails_on_parent(self):
        os.mkdir('u')
        with testenv.DirectoryChanger('u'):
            os.mkdir('.dlbroot')
            with dlb.ex.Context():
                with self.assertRaises(ValueError):
                    dlb.ex.Context.working_tree_path_of('../')


class ReprTest(unittest.TestCase):

    def test_repr_name_reflects_recommended_module(self):
        self.assertEqual(repr(dlb.ex.Context), "<class 'dlb.ex.Context'>")
        self.assertEqual(repr(dlb.ex._context._EnvVarDict), "<class 'dlb.ex.Context.EnvVarDict'>")


class ReadOnlyAccessTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_read_access_to_inactive_context_is_possible(self):
        with dlb.ex.Context():
            with dlb.ex.Context() as c1:
                c1.helper['a'] = '/a'
                with dlb.ex.Context() as c2:
                    c2.helper['b'] = '/b'
                    rc1 = dlb.ex.ReadOnlyContext(c1)
                    rc2 = dlb.ex.ReadOnlyContext(c2)
                    self.assertEqual(dlb.fs.Path('/a'), rc1.helper['a'])
                    self.assertEqual(dlb.fs.Path('/b'), rc2.helper['b'])
                self.assertEqual(dlb.fs.Path('/a'), rc1.helper['a'])
                self.assertEqual(dlb.fs.Path('/b'), rc2.helper['b'])
            self.assertEqual(dlb.fs.Path('/a'), rc1.helper['a'])
            self.assertEqual(dlb.fs.Path('/b'), rc2.helper['b'])

    def test_write_access_to_inactive_context_fails(self):
        with dlb.ex.Context() as c:
            c.helper['a'] = '/a'
            rc = dlb.ex.ReadOnlyContext(c)
            with self.assertRaises(TypeError):
                rc.helper['a'] = '/A'
            with self.assertRaises(TypeError):
                rc.env['a'] = '/A'

    def test_fails_without_active_context(self):
        with dlb.ex.Context() as c:
            pass
        with self.assertRaises(dlb.ex.NotRunningError):
            dlb.ex.ReadOnlyContext(c)

    def test_fails_for_redo_context(self):
        with dlb.ex.Context() as c:
            rc = dlb.ex.ReadOnlyContext(c)
            with self.assertRaises(TypeError) as cm:
                # noinspection PyTypeChecker
                dlb.ex.ReadOnlyContext(rc)
            self.assertEqual("'context' must be a Context object", str(cm.exception))


class ForgetOldInformationTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_nonpositive_age(self):
        orig = dlb.cf.max_dependency_age
        try:
            dlb.cf.max_dependency_age = datetime.timedelta(0)
            with self.assertRaises(ValueError) as cm:
                with dlb.ex.Context():
                    pass
            self.assertEqual("'dlb.cf.max_dependency_age' must be positive", str(cm.exception))
        finally:
            dlb.cf.max_dependency_age = orig

    def test_fails_for_integer(self):
        orig = dlb.cf.max_dependency_age
        try:
            dlb.cf.max_dependency_age = 12
            with self.assertRaises(TypeError) as cm:
                with dlb.ex.Context():
                    pass
            self.assertEqual("'dlb.cf.max_dependency_age' must be a datetime.timedelta object", str(cm.exception))
        finally:
            dlb.cf.max_dependency_age = orig

    def test_fails_for_too_large(self):
        orig = dlb.cf.max_dependency_age
        try:
            dlb.cf.max_dependency_age = datetime.timedelta.max
            regex = r"^'max_dependency_age' too large: datetime\.timedelta\(.+\)$"
            with self.assertRaisesRegex(ValueError, regex):
                with dlb.ex.Context():
                    pass
        finally:
            dlb.cf.max_dependency_age = orig

    def test_removes_older(self):
        orig = dlb.cf.max_dependency_age
        try:
            dlb.cf.max_dependency_age = datetime.timedelta(days=1001)

            with dlb.ex.Context():
                self.assertEqual(0, len(dlb.ex.Context.summary_of_latest_runs(max_count=3)))
            with dlb.ex.Context():
                self.assertEqual(1, len(dlb.ex.Context.summary_of_latest_runs(max_count=3)))
            with dlb.ex.Context():
                self.assertEqual(2, len(dlb.ex.Context.summary_of_latest_runs(max_count=3)))

            time.sleep(0.5)

            dlb.cf.max_dependency_age = datetime.timedelta(seconds=1e-6)
            with dlb.ex.Context():
                self.assertEqual(0, len(dlb.ex.Context.summary_of_latest_runs(max_count=3)))
        finally:
            dlb.cf.max_dependency_age = orig
