import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex
import dlb.ex.context
import tempfile
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


class ModuleTest(unittest.TestCase):

    def test_import(self):
        import dlb.ex.context
        self.assertEqual(['Context'], dlb.ex.context.__all__)
        self.assertTrue('Tool' in dir(dlb.ex))


class NestingTest(TemporaryDirectoryTestCase):

    def test_none_active_at_module_level(self):
        with self.assertRaises(dlb.ex.context.NoneActiveError):
            dlb.ex.Context.active

    def test_no_root_at_module_level(self):
        with self.assertRaises(dlb.ex.context.NoneActiveError):
            dlb.ex.Context.root

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

        with self.assertRaises(dlb.ex.context.NoneActiveError):
            dlb.ex.Context.active
        with self.assertRaises(dlb.ex.context.NoneActiveError):
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


class AttributeProtectionTest(unittest.TestCase):

    def test_active_attribute_is_readonly(self):
        with self.assertRaises(AttributeError):
            dlb.ex.Context.active = None

    def test_root_attribute_is_readonly(self):
        with self.assertRaises(AttributeError):
            dlb.ex.Context.root = None


class WorkingTreeRequirementTest(TemporaryDirectoryTestCase):

    def test_filenames_management_tree_are_portable(self):
        import dlb.fs
        dlb.fs.PortablePath(dlb.ex.context._MANAGEMENTTREE_DIR_NAME)
        dlb.fs.PortablePath(dlb.ex.context._MTIME_PROBE_FILE_NAME)
        dlb.fs.PortablePath(dlb.ex.context._RUNDB_FILE_NAME)

    def test_fails_if_dlbroot_does_not_exist(self):
        with self.assertRaises(dlb.ex.context.NoWorkingTree) as cm:
            with dlb.ex.Context(): pass

        self.assertIn(repr('.dlbroot'), str(cm.exception))
        self.assertIn('working tree', str(cm.exception))

    def test_fails_if_dlbroot_is_file(self):
        with open('.dlbroot', 'wb'):
            pass

        with self.assertRaises(dlb.ex.context.NoWorkingTree) as cm:
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

        with self.assertRaises(dlb.ex.context.NoWorkingTree) as cm:
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

    def test_paths_are_correct(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context() as c:
            self.assertEqual(os.path.abspath(os.getcwd()), c.root_path)
            self.assertEqual(os.path.join(os.path.abspath(os.getcwd()), '.dlbroot', 't'), c.temporary_path)

    def test_paths_inaccessible_without_active_context(self):
        os.mkdir('.dlbroot')

        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex.context.NoneActiveError) as cm:
            c.root_path
        with self.assertRaises(dlb.ex.context.NoneActiveError) as cm:
            c.temporary_path
