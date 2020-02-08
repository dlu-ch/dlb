import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex
import dlb.ex.context
import stat
import tempfile
import time
import unittest


class DirectoryChanger:
    def __init__(self, path):
        self._path = path

    def __enter__(self):
        self._original_path = os.getcwd()
        os.chdir(self._path)
        print(f'changed current working directory of process to {self._path!r}')

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self._original_path)
        print(f'changed current working directory of process back to {self._original_path!r}')


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
            print(f'changed current working directory of process to {self._temp_dir.name!r}')
        except:
            self._temp_dir.cleanup()

    def tearDown(self):
        if self._temp_dir:
            try:
                os.chdir(self._original_cwd)
                print(f'changed current working directory of process back to {self._original_cwd!r}')
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
            self.assertIs(c1.active, c1)
            self.assertIs(c1.root, c1)

            with dlb.ex.Context() as c2:
                self.assertIs(dlb.ex.Context.active, c2)
                self.assertIs(dlb.ex.Context.root, c1)
                self.assertIs(c1.active, c2)
                self.assertIs(c1.root, c1)

            self.assertIs(dlb.ex.Context.active, c1)
            self.assertIs(dlb.ex.Context.root, c1)

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.active
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.root

    def test_nesting_error_is_detected(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            with self.assertRaises(dlb.ex.context.NestingError):
                with dlb.ex.Context():
                    dlb.ex.context._contexts.pop()

    def test_meaningful_exception_on_attribute_error(self):
        os.mkdir('.dlbroot')

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
            self.assertTrue(os.path.islink('.dlbroot'))
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
            self.assertTrue(os.path.isfile('.dlbroot/o'))
            self.assertTrue(os.path.isdir('.dlbroot/t'))

    def test_temp_dir_is_recreated_if_nonempty_directory(self):
        os.mkdir('.dlbroot')

        os.mkdir('.dlbroot/t')
        os.mkdir('.dlbroot/t/c')
        with open('.dlbroot/t/a', 'wb'): pass
        with open('.dlbroot/t/c/b', 'wb'): pass

        sr0 = os.stat('.dlbroot/t')
        os.chmod('.dlbroot/t', stat.S_IMODE(sr0.st_mode) ^ stat.S_IXOTH)  # change permission
        sr1 = os.stat('.dlbroot/t')
        self.assertNotEqual(stat.S_IMODE(sr0.st_mode), stat.S_IMODE(sr1.st_mode))

        with dlb.ex.Context():
            self.assertTrue(os.path.isdir('.dlbroot/t'))
            self.assertTupleEqual((), tuple(os.listdir('.dlbroot/t')))
            sr2 = os.stat('.dlbroot/t')
            self.assertNotEqual(sr1, sr2)  # since inode could be reused, comparison of inodes would not work reliably

    def test_temp_dir_is_recreated_if_symlink(self):
        os.mkdir('.dlbroot')

        os.mkdir('.dlbroot/t_sysmlink_target')
        try:
            os.symlink('.dlbroot/t_sysmlink_target', '.dlbroot/t', target_is_directory=True)
            self.assertTrue(os.path.islink('.dlbroot/t'))
        except (NotImplementedError, PermissionError):  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None  # filesystem is not case-sensitive

        with dlb.ex.Context():
            self.assertTrue(os.path.isdir('.dlbroot/t'))
            self.assertFalse(os.path.islink('.dlbroot/t'))

    def test_mtime_probe_file_is_recreated_if_directory(self):
        os.mkdir('.dlbroot')

        os.mkdir('.dlbroot/o')
        os.mkdir('.dlbroot/o/c')
        with open('.dlbroot/o/a', 'wb'): pass
        with open('.dlbroot/o/c/b', 'wb'): pass

        with dlb.ex.Context():
            self.assertTrue(os.path.isfile('.dlbroot/o'))

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

    def test_meaningful_exception_on_permission_error_while_setup(self):
        os.mkdir('.dlbroot')
        os.mkdir('.dlbroot/t')
        os.mkdir('.dlbroot/t/c')

        os.chmod('.dlbroot/t', 0o000)

        regex = (
            r"(?m)"
            r"\Afailed to setup management tree for '.*'\n"
            r"  \| reason: .*'.+[/\\]\.dlbroot[/\\]t'.*\Z"
        )
        with self.assertRaisesRegex(dlb.ex.context.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass

        os.chmod('.dlbroot/t', 0o777)

    def test_meaningful_exception_on_permission_error_while_cleanup(self):
        os.mkdir('.dlbroot')

        regex = (
            r"(?m)"
            r"\Afailed to cleanup management tree for '.*'\n"
            r"  \| reason: .*'.+[/\\]\.dlbroot[/\\].*'.*\Z"
        )
        with self.assertRaisesRegex(dlb.ex.context.ManagementTreeError, regex):
            with dlb.ex.Context():
                os.mkdir('.dlbroot/t/c')
                os.chmod('.dlbroot/t', 0o000)
        os.chmod('.dlbroot/t', 0o777)


class PathsTest(TemporaryDirectoryTestCase):

    def test_root_is_unavailable_if_not_running(self):
        os.mkdir('.dlbroot')

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.root_path

        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex.context.NotRunningError) as cm:
            c.root_path

    def test_root_is_correct(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context() as c:
            self.assertIsInstance(c.root_path, dlb.fs.Path)
            self.assertEqual(os.path.abspath(os.getcwd()), str(c.root_path.native))
            cl = dlb.ex.Context.root_path
            self.assertEqual(c.root_path, cl)

    def test_path_class_is_correct(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            self.assertEqual(dlb.ex.Context.path_cls, dlb.fs.NoSpacePath)
            self.assertEqual(dlb.ex.Context.root_path.__class__, dlb.fs.NoSpacePath)
            with dlb.ex.Context(path_cls=dlb.fs.Path) as c:
                self.assertEqual(dlb.ex.Context.path_cls, dlb.fs.NoSpacePath)  # refers to root context
                self.assertEqual(c.path_cls, dlb.fs.Path)
                self.assertEqual(dlb.ex.Context.root_path.__class__, dlb.fs.NoSpacePath)

    def test_entering_fails_if_path_not_representabe(self):
        os.mkdir('x y')

        with DirectoryChanger('x y'):
            os.mkdir('.dlbroot')

            regex = (
                r"(?m)"
                r"\Acurrent directory violates imposed path restrictions\n"
                r"  \| reason: .*NoSpacePath.*'.+'.*\n"
                r"  \| move the working directory or choose a less restrictive path class for the root context\Z"
            )
            with self.assertRaisesRegex(ValueError, regex):
                with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
                    pass

            with dlb.ex.Context():  # no exception
                regex = (
                    r"(?m)"
                    r"\Aworking tree's root path violates path restrictions imposed by this context\n"
                    r"  \| reason: .*NoSpacePath.*'.+'.*\n"
                    r"  \| move the working directory or choose a less restrictive path class for the root context\Z"
                )
                with self.assertRaisesRegex(ValueError, regex):
                    with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
                        pass


class WorkingTreeTimeTest(TemporaryDirectoryTestCase):

    def test_time_is_unavailable_if_not_running(self):
        os.mkdir('.dlbroot')

        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.working_tree_time_ns

    def test_time_does_change_after_at_most_15secs(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context():
            start_time = time.time()
            start_working_tree_time = dlb.ex.Context.working_tree_time_ns

            while dlb.ex.Context.working_tree_time_ns == start_working_tree_time:
                self.assertLessEqual(time.time() - start_time, 15.0)
                time.sleep(0.015)  # typical effective working tree time resolution: 10 ms

    def test_exit_does_delay_to_next_change(self):
        os.mkdir('.dlbroot')

        for i in range(10):  # might also pass by chance (transition of working tree time too close at exit context)
            with dlb.ex.Context():
                enter_time = dlb.ex.Context.working_tree_time_ns
            with dlb.ex.Context():
                exit_time = dlb.ex.Context.working_tree_time_ns
            self.assertNotEqual(enter_time, exit_time)


class RunDatabaseTest(TemporaryDirectoryTestCase):

    def test_nonexisting_is_created(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            os.path.isfile('.dlbroot/runs.sqlite')


class ProcessLockTest(TemporaryDirectoryTestCase):

    def test_fail_if_lock_dir_exists(self):
        os.mkdir('.dlbroot')
        os.mkdir('.dlbroot/lock')

        regex = (
            r"(?m)"
            r"\Acannot aquire lock for exclusive access to working tree '.*'\n"
            r"  \| reason: .*'.+[/\\]\.dlbroot[/\\]lock'.*\n"
            r"  \| to break the lock \(if you are sure no other dlb process is running\): "
            r"remove '.*[/\\]\.dlbroot[/\\]lock'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.context.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass


    def test_meaningful_exception_on_permission_error(self):
        os.mkdir('.dlbroot')

        os.chmod('.dlbroot', 0o000)

        regex = (
            r"(?m)"
            r"\Acannot aquire lock for exclusive access to working tree '.*'\n"
            r"  \| reason: .*'.+[/\\]\.dlbroot[/\\]lock'.*\n"
            r"  \| to break the lock \(if you are sure no other dlb process is running\): "
            r"remove '.*[/\\]\.dlbroot[/\\]lock'\Z"
        )
        with self.assertRaisesRegex(dlb.ex.context.ManagementTreeError, regex):
            with dlb.ex.Context():
                pass

        os.chmod('.dlbroot', 0o777)



class TemporaryFilesystemObjectsTest(TemporaryDirectoryTestCase):

    def test_creates_regular_file(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context():
            t = dlb.ex.Context.root_path / '.dlbroot/t'

            p = dlb.ex.Context.create_temporary()
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertFalse(p.is_dir())
            self.assertTrue(os.path.isfile(p.native))
            self.assertEqual(t, os.path.dirname(p.native))

            p = dlb.ex.Context.create_temporary(is_dir=False, suffix='.o', prefix='aha')
            self.assertTrue(os.path.isfile(p.native))
            self.assertEqual(t, os.path.dirname(p.native))
            self.assertTrue(p.parts[-1].startswith('aha'), p)
            self.assertTrue(p.parts[-1].endswith('.o'), p)

        self.assertFalse(os.path.exists('.dlbroot/t'))

    def test_creates_directory(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context():
            t = dlb.ex.Context.root_path / '.dlbroot/t'
            p = dlb.ex.Context.create_temporary(is_dir=True)
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(p.is_dir())
            self.assertTrue(os.path.isdir(p.native))
            self.assertEqual(t, os.path.dirname(p.native))

            p = dlb.ex.Context.create_temporary(is_dir=True, suffix='.o', prefix='aha')
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(os.path.isdir(p.native))
            self.assertEqual(t, os.path.dirname(p.native))
            self.assertTrue(p.parts[-1].startswith('aha'), p)
            self.assertTrue(p.parts[-1].endswith('.o'), p)

        self.assertFalse(os.path.exists('.dlbroot/t'))

    def test_fails_for_if_not_running(self):
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.create_temporary()
        with self.assertRaises(dlb.ex.context.NotRunningError):
            dlb.ex.Context.create_temporary(is_dir=True)

    def test_fails_for_bytes_prefix_or_suffix(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            with self.assertRaises(TypeError):
                dlb.ex.Context.create_temporary(prefix=b'x')
            with self.assertRaises(TypeError):
                dlb.ex.Context.create_temporary(suffix=b'y')

    def test_fails_for_empty_prefix(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(prefix='')
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(is_dir=True, prefix='')

    def test_fails_for_path_separator_in_prefix(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(prefix='x/')
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(is_dir=True, prefix='x/../')
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(suffix='x/')
            with self.assertRaises(ValueError):
                dlb.ex.Context.create_temporary(is_dir=True, suffix='x/../')

    def test_fails_if_path_not_representabe(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            regex = (
                r"(?m)"
                r"\Apath violates imposed path restrictions\n"
                r"  \| reason: .*NoSpacePath.*'.+'.*\n"
                r"  \| check specified 'prefix' and 'suffix'\Z"
            )
            with self.assertRaisesRegex(ValueError, regex):
                dlb.ex.Context.create_temporary(suffix='x y')


class ManagedTreePathTest(TemporaryDirectoryTestCase):

    def test_root_is_managed_tree_path(self):
        os.mkdir('.dlbroot')
        os.mkdir('a')
        os.mkdir('a/b')
        with open('a/b/c', 'w'):
            pass

        with dlb.ex.Context(dlb.fs.NoSpacePath):
            p = dlb.ex.Context.get_managed_tree_path(dlb.ex.Context.root_path)

            self.assertIsInstance(p, dlb.fs.NoSpacePath)

            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, dlb.fs.Path('.', is_dir=True))

            p = dlb.ex.Context.get_managed_tree_path(os.path.join(dlb.ex.Context.root_path.native.raw, 'a/b/'))
            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, dlb.fs.Path('a/b', is_dir=True))

            p = dlb.ex.Context.get_managed_tree_path(os.path.join(dlb.ex.Context.root_path.native.raw, 'a/b/c'))
            self.assertFalse(p.is_absolute())
            self.assertTrue(p.is_normalized())
            self.assertEqual(p, dlb.fs.Path('a/b/c', is_dir=False))

    def test_fails_on_nonexisting(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            with self.assertRaises(FileNotFoundError):
                dlb.ex.Context.get_managed_tree_path('a/b')

    def test_fails_on_parent(self):
        os.mkdir('u')
        with DirectoryChanger('u'):
            os.mkdir('.dlbroot')
            with dlb.ex.Context():
                with self.assertRaises(ValueError):
                    dlb.ex.Context.get_managed_tree_path('../')

    def test_fails_on_management_tree(self):
        os.mkdir('.dlbroot')
        os.mkdir('.dlbroot/u')

        with dlb.ex.Context():
            with self.assertRaises(ValueError):
                dlb.ex.Context.get_managed_tree_path('.dlbroot')
            with self.assertRaises(ValueError):
                dlb.ex.Context.get_managed_tree_path('.dlbroot/u')

    def test_fail_if_dir_path_to_nondir(self):
        os.mkdir('.dlbroot')
        os.mkdir('d')
        with open('f', 'w'):
            pass

        with dlb.ex.Context():
            self.assertEqual(dlb.ex.Context.get_managed_tree_path(''), dlb.fs.Path('.'))
            self.assertEqual(dlb.ex.Context.get_managed_tree_path('f/..'), dlb.fs.Path('.'))

            regex = r"\Aform of 'path' does not match the type of filesystem object: '.*'\Z"
            with self.assertRaisesRegex(ValueError, regex):
                dlb.ex.Context.get_managed_tree_path('f/')
            with self.assertRaisesRegex(ValueError, regex):
                dlb.ex.Context.get_managed_tree_path('f/.')
            with self.assertRaisesRegex(ValueError, regex):
                dlb.ex.Context.get_managed_tree_path(dlb.fs.Path('f', is_dir=True))

        with dlb.ex.Context():
            dlb.ex.Context.get_managed_tree_path('d')  # ok (like POSIX path resolution)
            with self.assertRaises(ValueError):
                dlb.ex.Context.get_managed_tree_path(dlb.fs.Path('d', is_dir=False))

    def test_fail_if_unsupported_type(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context():
            with self.assertRaises(TypeError) as cm:
                dlb.ex.Context.get_managed_tree_path(3)
            self.assertEqual(str(cm.exception), "'path' must be 'str' or 'dlb.fs.Path'")

    def test_fail_if_unrepresentable(self):
        os.mkdir('.dlbroot')
        os.mkdir('a b')

        with dlb.ex.Context(path_cls=dlb.fs.NoSpacePath):
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.get_managed_tree_path('a b')

