import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex
import dlb.ex.context
import tempfile
import time
import unittest


class TemporaryDirectoryTestCase(unittest.TestCase):  # change to temporary directory during test
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_cwd = None
        self._temp_dir = None

    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.TemporaryDirectory()
        try:
            os.chdir(self._temp_dir.name)
            print(f'changed current working directory of process to {self._temp_dir.name}')
        except:
            self._temp_dir.cleanup()

    def tearDown(self):
        if self._temp_dir:
            try:
                os.chdir(self._original_cwd)
                print(f'changed current working directory of process back to {self._original_cwd}')
            finally:
                self._temp_dir.cleanup()


class TechnicalInterfaceTest(unittest.TestCase):

    def test_import(self):
        import dlb.ex.context
        self.assertEqual(['Context'], dlb.ex.context.__all__)
        self.assertTrue('Tool' in dir(dlb.ex))

    def test_attributes_of_contextmeta_and_rootsspecifics_to_not_clash(self):
        rs = set(n for n in dlb.ex.context._RootSpecifics.__dict__ if not n.startswith('_'))
        mc = set(n for n in dlb.ex.context._ContextMeta.__dict__ if not n.startswith('_'))
        self.assertEqual(set(), rs.intersection(mc))

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


class NestingTest(TemporaryDirectoryTestCase):

    def test_fails_if_not_running(self):
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.root
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.active

    def test_can_by_nested(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c1:
            self.assertIs(dlb.ex.Context.active, c1)
            self.assertIs(dlb.ex.Context.root, c1)

            with dlb.ex.Context() as c2:
                self.assertIs(dlb.ex.Context.active, c2)
                self.assertIs(dlb.ex.Context.root, c1)

            self.assertIs(dlb.ex.Context.active, c1)
            self.assertIs(dlb.ex.Context.root, c1)

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.active
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.root

    def test_nesting_error_is_detected(self):
        import dlb.ex.context

        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            with self.assertRaises(dlb.ex.context.NestingError):
                with dlb.ex.Context():
                    dlb.ex.context._contexts.pop()


class ReuseTest(TemporaryDirectoryTestCase):

    def test_context_can_be_reused(self):
        os.mkdir('.dlbroot')
        c = dlb.ex.Context()
        with c:
            pass
        with c:
            pass


class WorkingTreeRequirementTest(TemporaryDirectoryTestCase):

    def test_management_tree_paths_are_portable(self):
        import dlb.fs
        dlb.fs.PortablePath(dlb.ex.context._MANAGEMENTTREE_DIR_NAME)
        dlb.fs.PortablePath(dlb.ex.context._MTIME_PROBE_FILE_NAME)
        dlb.fs.PortablePath(dlb.ex.context._RUNDB_FILE_NAME)

    def test_fails_if_dlbroot_does_not_exist(self):
        with self.assertRaises(dlb.ex.context.NoWorkingTreeError) as cm:
            with dlb.ex.Context(): pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))

    def test_fails_if_dlbroot_is_file(self):
        with open('.dlbroot', 'wb'):
            pass

        with self.assertRaises(dlb.ex.context.NoWorkingTreeError) as cm:
            with dlb.ex.Context(): pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))

    def test_fails_if_dlbroot_is_symlink_to_dir(self):
        os.mkdir('dlbroot_sysmlink_target')
        try:
            os.symlink('dlbroot_sysmlink_target', '.dlbroot', target_is_directory=True)
        except (NotImplementedError, PermissionError):  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None  # filesystem is not case-sensitive

        with self.assertRaises(dlb.ex.context.NoWorkingTreeError) as cm:
            with dlb.ex.Context(): pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))


class ManagementTreeSetupTest(TemporaryDirectoryTestCase):

    def test_missing_filesystem_objects_are_created(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            os.path.isfile('.dlbroot/o')
            os.path.isdir('.dlbroot/t')

    def test_temp_dir_is_recreated(self):
        os.mkdir('.dlbroot')

        os.mkdir('.dlbroot/t')
        os.mkdir('.dlbroot/t/c')
        with open('.dlbroot/t/a', 'wb'): pass
        with open('.dlbroot/t/c/b', 'wb'): pass
        oldsr = os.lstat('.dlbroot/t')

        with dlb.ex.Context():
            os.path.isdir('.dlbroot/t')
            self.assertFalse(os.path.samestat(oldsr, os.lstat('.dlbroot/t')))

    def test_temp_dir_symlink_is_recreated(self):
        os.mkdir('.dlbroot')

        os.mkdir('.dlbroot/t_sysmlink_target')
        try:
            os.symlink('.dlbroot/t_sysmlink_target', '.dlbroot/t', target_is_directory=True)
        except (NotImplementedError, PermissionError):  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None  # filesystem is not case-sensitive

        oldsr = os.lstat('.dlbroot/t')
        with dlb.ex.Context():
            os.path.isdir('.dlbroot/t')
            self.assertFalse(os.path.samestat(oldsr, os.lstat('.dlbroot/t')))

    def test_mtime_probe_file_is_recreated(self):
        os.mkdir('.dlbroot')

        os.mkdir('.dlbroot/o')
        os.mkdir('.dlbroot/o/c')
        with open('.dlbroot/o/a', 'wb'): pass
        with open('.dlbroot/o/c/b', 'wb'): pass
        oldsr = os.lstat('.dlbroot/o')

        with dlb.ex.Context():
            self.assertTrue(os.path.isfile('.dlbroot/o'))
            self.assertFalse(os.path.samestat(oldsr, os.lstat('.dlbroot/o')))

    def test_mtime_probe_uppercase_file_is_removed(self):
        os.mkdir('.dlbroot')

        with open('.dlbroot/o', 'xb'): pass
        try:
            with open('.dlbroot/O', 'xb'): pass
        except FileExistsError:
            raise unittest.SkipTest from None  # filesystem is not case-sensitive
        with dlb.ex.Context():
            self.assertTrue(os.path.isfile('.dlbroot/o'))
            self.assertFalse(os.path.exists('.dlbroot/O'))


class PathsTest(TemporaryDirectoryTestCase):

    def test_paths_are_unavailable_if_not_running(self):
        os.mkdir('.dlbroot')

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.root_path
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.temporary_path

        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex.context.NotRunningError) as cm:
            c.root_path
        with self.assertRaises(dlb.ex.context.NotRunningError) as cm:
            c.temporary_path

    def test_paths_are_correct(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context() as c:
            self.assertEqual(os.path.abspath(os.getcwd()), c.root_path)
            cl = dlb.ex.Context.root_path
            self.assertEqual(c.root_path, cl)
            self.assertEqual(os.path.join(os.path.abspath(os.getcwd()), '.dlbroot', 't'), c.temporary_path)


class WorkingTreeTimeTest(TemporaryDirectoryTestCase):

    def test_time_is_unavailable_if_not_running(self):
        os.mkdir('.dlbroot')

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.working_tree_time_ns

    def test_time_does_change_after_at_most_5secs(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context():
            start_time = time.time_ns()
            start_working_tree_time = dlb.ex.Context.working_tree_time_ns

            while dlb.ex.Context.working_tree_time_ns <= start_working_tree_time:
                self.assertLessEqual(time.time_ns() - start_time, 10_000_000)
                time.sleep(0.015)  # typical effective working tree time resolution: 10 ms

    def test_exit_does_delay_to_next_change(self):
        os.mkdir('.dlbroot')

        for i in range(10):  # might also pass by chance (transition of working tree time too close at exit context)
            with dlb.ex.Context():
                enter_time = dlb.ex.Context.working_tree_time_ns
            with dlb.ex.Context():
                exit_time = dlb.ex.Context.working_tree_time_ns
            self.assertNotEqual(enter_time, exit_time)
