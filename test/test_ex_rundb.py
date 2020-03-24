# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex.rundb
import dlb.ex.worktree
import datetime
import stat
import collections
import contextlib
import marshal
import unittest
import tools_for_test


class SchemaVersionTest(unittest.TestCase):

    def test_is_nonempty_tuple_of_nonnegative_ints(self):
        v = dlb.ex.rundb.SCHEMA_VERSION
        self.assertIsInstance(v, tuple)
        self.assertGreater(len(v), 1)
        for c in v:
            self.assertIsInstance(c, int)
            self.assertGreaterEqual(c, 0)


class CreationTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_file_exists_after_construction(self):
        try:
            os.mkdir('a:b')
        except OSError:
            raise unittest.SkipTest from None  # POSIX does not required the support of ':' in a file name
        with contextlib.closing(dlb.ex.rundb.Database(':memory:')):
            os.path.isfile(':memory:')

    def test_can_be_constructed_multiple_times(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')):
            pass

        os.path.isfile('runs.sqlite')

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')):
            pass


class CreationWithPermissionProblemTest(tools_for_test.TemporaryDirectoryWithChmodTestCase):

    def test_fails_with_meaningful_message_on_permission_problem_when_nonexistent(self):
        os.mkdir('t')
        os.chmod('t', 0x000)

        try:
            regex = (
                r"(?m)\A"
                r"could not open non-existent run-database: '.+'\n"
                r"  \| reason: sqlite3.OperationalError: unable to open database file\n"
                r"  \| check access permissions\Z"
            )
            with self.assertRaisesRegex(dlb.ex.DatabaseError, regex):
                with contextlib.closing(dlb.ex.rundb.Database('t/runs.sqlite')):
                    pass
        finally:
            os.chmod('t', 0x777)


class ToolInstanceDbidTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_is_created_as_needed(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't1', b'ti1')
            self.assertIsInstance(tool_dbid1, int)

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't1', b'ti2')
            self.assertNotEqual(tool_dbid2, tool_dbid1)

            tool_dbid3 = rundb.get_and_register_tool_instance_dbid(b't2', b'ti1')
            self.assertNotEqual(tool_dbid3, tool_dbid1)
            self.assertNotEqual(tool_dbid3, tool_dbid2)

    def test_returns_same_of_called_more_than_once(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't1', b'ti1')
            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't1', b'ti1')
            self.assertEqual(tool_dbid2, tool_dbid1)


class RunDbidTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_changes_between_runs(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            run_dbid1 = rundb.run_dbid
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            run_dbid2 = rundb.run_dbid
        self.assertNotEqual(run_dbid1, run_dbid2)


class EncodePathTest(unittest.TestCase):

    def test_is_str(self):
        self.assertIsInstance(dlb.ex.rundb.encode_path(dlb.fs.Path('.')), str)

    def test_is_correct(self):
        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a'))
        self.assertEqual('a/', encoded_path)

        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a/'))
        self.assertEqual('a/', encoded_path)

        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('./a/b/c/'))
        self.assertTrue(dlb.ex.rundb.is_encoded_path(encoded_path))

        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('.'))
        self.assertEqual('', encoded_path)

    def test_is_valid(self):
        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a'))
        self.assertTrue(dlb.ex.rundb.is_encoded_path(encoded_path))

        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('./a/b/c/'))
        self.assertTrue(dlb.ex.rundb.is_encoded_path(encoded_path))

        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('.'))
        self.assertTrue(dlb.ex.rundb.is_encoded_path(encoded_path))

    def test_root_is_prefix_of_all(self):
        encoded_path_root = dlb.ex.rundb.encode_path(dlb.fs.Path('.'))
        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a'))
        self.assertTrue(encoded_path.startswith(encoded_path_root))

    def test_fails_for_str(self):
        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            dlb.ex.rundb.encode_path('/a/b')

    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.encode_path(dlb.fs.Path('/a/b'))

    def test_fails_for_non_normalized(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/c/../'))
        with self.assertRaises(ValueError):
            dlb.ex.rundb.encode_path(dlb.fs.Path('..'))


class DecodeEncodedPathTest(unittest.TestCase):

    def test_runtrip_works(self):
        paths = [
            dlb.fs.Path('.'),
            dlb.fs.Path(r'a\b/c\d/'),
            dlb.fs.Path(r'a/b/'),
        ]
        paths_roundtrip = [
            dlb.ex.rundb.decode_encoded_path(dlb.ex.rundb.encode_path(p), is_dir=True)
            for p in paths
        ]
        self.assertEqual(paths, paths_roundtrip)

    def test_fails_for_encoded_path_with_dotdot(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_path('a/../')
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_path('a/../b/')

    def test_fails_for_encoded_path_withot_trailing_slash(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_path('a/b')

    def test_fails_for_encoded_path_with_slash(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_path('/')

    def test_isdir_is_correct(self):
        self.assertFalse(dlb.ex.rundb.decode_encoded_path(dlb.ex.rundb.encode_path(
            dlb.fs.Path('a/b')), is_dir=False).is_dir())
        self.assertTrue(dlb.ex.rundb.decode_encoded_path(dlb.ex.rundb.encode_path(
            dlb.fs.Path('a/b')), is_dir=True).is_dir())
        self.assertTrue(dlb.ex.rundb.decode_encoded_path(dlb.ex.rundb.encode_path(
            dlb.fs.Path('.')), is_dir=False).is_dir())


class EncodeFsobjectMemoTest(unittest.TestCase):

    def test_fails_for_none(self):
        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            dlb.ex.rundb.encode_fsobject_memo(None)

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            dlb.ex.rundb.encode_fsobject_memo(b'')

    def test_fails_for_noninteger_mtime(self):
        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            m = dlb.ex.rundb.FilesystemObjectMemo(
                stat=dlb.ex.rundb.FilesystemStatSummary(mode=stat.S_IFREG, size=0, mtime_ns=1.25, uid=0, gid=0),
                symlink_target=None)
            dlb.ex.rundb.encode_fsobject_memo(m)

    def test_fails_for_symlink_without_target(self):
        with self.assertRaises(TypeError):
            m = dlb.ex.rundb.FilesystemObjectMemo(
                stat=dlb.ex.rundb.FilesystemStatSummary(mode=stat.S_IFLNK, size=0, mtime_ns=0, uid=0, gid=0),
                symlink_target=None)
            dlb.ex.rundb.encode_fsobject_memo(m)

        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            m = dlb.ex.rundb.FilesystemObjectMemo(
                stat=dlb.ex.rundb.FilesystemStatSummary(mode=stat.S_IFLNK, size=0, mtime_ns=0, uid=0, gid=0),
                symlink_target=b'')
            dlb.ex.rundb.encode_fsobject_memo(m)

    def test_fails_for_nosymlink_with_target(self):
        with self.assertRaises(ValueError):
            m = dlb.ex.rundb.FilesystemObjectMemo(
                stat=dlb.ex.rundb.FilesystemStatSummary(mode=stat.S_IFREG, size=0, mtime_ns=0, uid=0, gid=0),
                symlink_target='/')
            dlb.ex.rundb.encode_fsobject_memo(m)

    def test_returns_nonempty_for_non_existent(self):
        m = dlb.ex.rundb.FilesystemObjectMemo()
        e = dlb.ex.rundb.encode_fsobject_memo(m)
        self.assertNotEqual(b'', e)


class DecodeEncodedFsobjectMemoTest(unittest.TestCase):

    def test_fails_for_none(self):
        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            dlb.ex.rundb.decode_encoded_fsobject_memo(None)

    def test_fails_for_str(self):
        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            dlb.ex.rundb.decode_encoded_fsobject_memo('')

    def test_runtrip_works(self):
        paths = [
            dlb.ex.rundb.FilesystemObjectMemo(),
            dlb.ex.rundb.FilesystemObjectMemo(
                stat=dlb.ex.rundb.FilesystemStatSummary(mode=stat.S_IFREG, size=2, mtime_ns=3, uid=4, gid=5),
                symlink_target=None),
            dlb.ex.rundb.FilesystemObjectMemo(
                stat=dlb.ex.rundb.FilesystemStatSummary(
                    mode=stat.S_IFLNK | stat.S_IRWXG, size=2, mtime_ns=3, uid=4, gid=5),
                symlink_target='/a/b/c/')
        ]
        paths_roundtrip = [
            dlb.ex.rundb.decode_encoded_fsobject_memo(dlb.ex.rundb.encode_fsobject_memo(m))
            for m in paths
        ]
        self.assertEqual(paths, paths_roundtrip)

    def test_fails_for_invalid_encoded(self):
        m = dlb.ex.rundb.FilesystemObjectMemo(
             stat=dlb.ex.rundb.FilesystemStatSummary(mode=stat.S_IFREG, size=2, mtime_ns=3, uid=4, gid=5),
             symlink_target=None)

        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_fsobject_memo(marshal.dumps(0))  # int instead of tuple

        b = dlb.ex.rundb.encode_fsobject_memo(m)
        t = marshal.loads(b)
        t = (t[0], '1') + t[2:]
        b = marshal.dumps(t)
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_fsobject_memo(b)  # str element instead of int element

        b = dlb.ex.rundb.encode_fsobject_memo(m)
        t = marshal.loads(b)
        t = t + (7,)
        b = marshal.dumps(t)
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_fsobject_memo(b)  # too many elements

        b = dlb.ex.rundb.encode_fsobject_memo(m)
        t = marshal.loads(b)
        t = t[:-1] + ('a',)
        b = marshal.dumps(t)
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_fsobject_memo(b)  # symlink target for non-symlink

        m = dlb.ex.rundb.FilesystemObjectMemo(
             stat=dlb.ex.rundb.FilesystemStatSummary(mode=stat.S_IFLNK, size=2, mtime_ns=3, uid=4, gid=5),
             symlink_target='a')
        b = dlb.ex.rundb.encode_fsobject_memo(m)
        t = marshal.loads(b)
        t = t[:-1] + (None,)
        b = marshal.dumps(t)
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_encoded_fsobject_memo(b)  # non symlink target for symlink


class EncodeDatetimeTest(tools_for_test.TemporaryDirectoryTestCase):
    def test_is_correct_for_typical(self):
        d = datetime.datetime(year=2020, month=3, day=19, hour=11, minute=20, second=25, microsecond=10000)
        self.assertEqual('20200319T112025.01', dlb.ex.rundb.encode_datetime(d))

        # rationale:
        assert '20200319T112025.01' < '20200319T112025.010'
        assert '20200319T112025.01' < '20200319T112025.0101'

    def test_now_is_correct(self):
        t = datetime.datetime.utcnow()
        s = dlb.ex.rundb.encode_datetime(t)
        self.assertRegex(s, r'^[0-9]{8}T[0-9]{6}\.[0-9]+$')


class DecodeDatetimeTest(tools_for_test.TemporaryDirectoryTestCase):
    def test_is_correct_for_typical(self):
        d = datetime.datetime(year=2020, month=3, day=19, hour=11, minute=20, second=25, microsecond=10000)
        self.assertEqual(d, dlb.ex.rundb.decode_datetime('20200319T112025.01'))

    def test_roundtrip_is_lossless(self):
        t0 = datetime.datetime.utcnow()
        s = dlb.ex.rundb.encode_datetime(t0)
        t1 = dlb.ex.rundb.decode_datetime(s)
        self.assertEqual(t1, t0)

    def test_fails_for_empty(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_datetime('')

    def test_fails_with_utc_suffix(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_datetime('20200319T112025Z')
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_datetime('20200319T112025+00:00')

    def test_fails_without_time_separator(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.decode_datetime('20200319112025')


class UpdateAndGetFsobjectInputTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_non_existent_is_added(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', b'i')

            encoded_path1 = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/c'))
            encoded_path2 = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/'))
            rundb.update_dependencies(tool_dbid, info_by_encoded_path={
                encoded_path1: (False, b'?'),
                encoded_path2: (True, None)
            })

            rows = rundb.get_fsobject_inputs(tool_dbid)
            self.assertEqual({encoded_path1: (False, b'?'), encoded_path2: (True, None)}, rows)

            rows = rundb.get_fsobject_inputs(tool_dbid, False)
            self.assertEqual({encoded_path1: (False, b'?')}, rows)

            rows = rundb.get_fsobject_inputs(tool_dbid, True)
            self.assertEqual({encoded_path2: (True, None)}, rows)

    def test_existing_is_replaced(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', b'i')

            encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/c'))
            rundb.update_dependencies(tool_dbid, info_by_encoded_path={encoded_path: (True, b'1')})
            rundb.update_dependencies(tool_dbid, info_by_encoded_path={encoded_path: (False, b'234')})

            rows = rundb.get_fsobject_inputs(tool_dbid)
            self.assertEqual({encoded_path: (False, b'234')}, rows)

    def test_fails_if_tool_dbid_does_no_exist(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite',
                                                      suggestion_if_database_error="don't panic")) as rundb:
            with self.assertRaises(dlb.ex.DatabaseError) as cm:
                encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/c'))
                rundb.update_dependencies(12, info_by_encoded_path={encoded_path: (True, b'')})

            msg = (
                "run-database access failed\n"
                "  | sqlite3.IntegrityError: FOREIGN KEY constraint failed\n"
                "  | don't panic"
            )
            self.assertEqual(msg, str(cm.exception))

    def test_update_fails_for_invalid_encoded_path(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            with self.assertRaises(ValueError):
                # noinspection PyTypeChecker
                rundb.update_dependencies(12, info_by_encoded_path={3: (True, b'')})
            with self.assertRaises(ValueError):
                rundb.update_dependencies(12, info_by_encoded_path={'/3': (True, b'')})

    def test_update_fails_for_invalid_encoded_memo(self):
        encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/c'))

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                rundb.update_dependencies(12, info_by_encoded_path={encoded_path: (True, '')})


class DeclareFsobjectInputAsModifiedTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_scenario1(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            # 1. insert explicit and non-explicit input dependencies for different tool instances

            modified_encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b'))

            encoded_paths = [
                dlb.ex.rundb.encode_path(dlb.fs.Path(s))
                for s in [
                    '.',
                    'c/a/b',
                    'a/b_',
                    'a/B',
                    
                    # these have modified_encoded_path as prefix:
                    'a/b',
                    'a/b/c42',
                    'a/b/c/d',
                    'a/b/c/d/e'
                ]
            ]
            
            encoded_paths1_explicit = [
                encoded_paths[1],
                encoded_paths[3],
                encoded_paths[5]   # *+
            ]
            encoded_paths1_nonexplicit = [
                encoded_paths[0],
                encoded_paths[2],
                encoded_paths[4],  # *+
                encoded_paths[6],  # *
            ]
            self.assertEqual(set(), set(encoded_paths1_explicit) & set(encoded_paths1_nonexplicit))

            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            d = {encoded_path: (True, b'e1') for encoded_path in encoded_paths1_explicit}
            d.update({encoded_path: (False, b'n1') for encoded_path in encoded_paths1_nonexplicit})
            rundb.update_dependencies(tool_dbid1, info_by_encoded_path=d)

            encoded_paths2_explicit = [
                encoded_paths[0],
                encoded_paths[2],
                encoded_paths[3],
                encoded_paths[5]   # *
            ]
            encoded_paths2_nonexplicit = [
                encoded_paths[1],
                encoded_paths[6],  # *
            ]
            self.assertEqual(set(), set(encoded_paths2_explicit) & set(encoded_paths2_nonexplicit))

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't', b'i2')
            d = {encoded_path: (True, b'e2') for encoded_path in encoded_paths2_explicit}
            d.update({encoded_path: (False, b'n2') for encoded_path in encoded_paths2_nonexplicit})
            rundb.update_dependencies(tool_dbid2, info_by_encoded_path=d)

            self.assertEqual(len(encoded_paths1_explicit) + len(encoded_paths1_nonexplicit),
                             len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(len(encoded_paths2_explicit) + len(encoded_paths2_nonexplicit),
                             len(rundb.get_fsobject_inputs(tool_dbid2)))

            # 2.1 define some as modified

            rundb.update_dependencies(tool_dbid1, encoded_paths_of_modified=[modified_encoded_path])

            # 2.2 check result

            encoded_paths1 = rundb.get_fsobject_inputs(tool_dbid1)
            self.assertEqual({
                encoded_paths[0]: (False, b'n1'),
                encoded_paths[1]: (True,  b'e1'),
                encoded_paths[2]: (False, b'n1'),
                encoded_paths[3]: (True,  b'e1'),
                encoded_paths[4]: (False, None),
                encoded_paths[5]: (True,  None),
                encoded_paths[6]: (False, None)
            }, encoded_paths1)

            encoded_paths2 = rundb.get_fsobject_inputs(tool_dbid2)
            self.assertEqual({
                encoded_paths[0]: (True,  b'e2'),
                encoded_paths[1]: (False, b'n2'),
                encoded_paths[2]: (True,  b'e2'),
                encoded_paths[3]: (True,  b'e2'),
                encoded_paths[5]: (True,  None),
                encoded_paths[6]: (False, None)
            }, encoded_paths2)

            # 3.1 define _all_ as modified

            # managed tree's root...
            rundb.update_dependencies(tool_dbid1, encoded_paths_of_modified=[encoded_paths[0]])

            # 3.2 check result

            encoded_paths1 = rundb.get_fsobject_inputs(tool_dbid1)
            self.assertEqual({
                encoded_paths[0]: (False, None),
                encoded_paths[1]: (True,  None),
                encoded_paths[2]: (False, None),
                encoded_paths[3]: (True,  None),
                encoded_paths[4]: (False, None),
                encoded_paths[5]: (True,  None),
                encoded_paths[6]: (False, None)
            }, encoded_paths1)

            encoded_paths2 = rundb.get_fsobject_inputs(tool_dbid2)
            self.assertEqual({
                encoded_paths[0]: (True,  None),
                encoded_paths[1]: (False, None),
                encoded_paths[2]: (True,  None),
                encoded_paths[3]: (True,  None),
                encoded_paths[5]: (True,  None),
                encoded_paths[6]: (False, None)
            }, encoded_paths2)

    def test_scenario2(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            with self.assertRaises(ValueError):
                rundb.update_dependencies(0, encoded_paths_of_modified='..')


class ReplaceFsInputsTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_is_correct_after_success(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            tool_dbid0 = rundb.get_and_register_tool_instance_dbid(b't', b'i0')
            rundb.update_dependencies(tool_dbid0, info_by_encoded_path={
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'0')
            })

            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_dependencies(tool_dbid, info_by_encoded_path={
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'1'),
                dlb.ex.rundb.encode_path(dlb.fs.Path('b')): (False, b'1')
            })

            info_by_encoded_path = {
                dlb.ex.rundb.encode_path(dlb.fs.Path('b')): (True, b'3'),
                dlb.ex.rundb.encode_path(dlb.fs.Path('c')): (False, b'4')
            }
            rundb.update_dependencies(tool_dbid, info_by_encoded_path=info_by_encoded_path)

            self.assertEqual(info_by_encoded_path, rundb.get_fsobject_inputs(tool_dbid))
            self.assertEqual({
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'0')
            }, rundb.get_fsobject_inputs(tool_dbid0)) # input dependencies of tool_dbid0 are unchanged

    def test_is_unchanged_after_fail(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_dependencies(tool_dbid, info_by_encoded_path={
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'1'),
                dlb.ex.rundb.encode_path(dlb.fs.Path('b')): (False, b'1')
            })

            info_by_encoded_path = collections.OrderedDict([
                (dlb.ex.rundb.encode_path(dlb.fs.Path('b')), (True, b'3')),
                (None, (False, b'4'))
            ])
            with self.assertRaises(ValueError):
                rundb.update_dependencies(tool_dbid, info_by_encoded_path=info_by_encoded_path)

            self.assertEqual({
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'1'),
                dlb.ex.rundb.encode_path(dlb.fs.Path('b')): (False, b'1')
            }, rundb.get_fsobject_inputs(tool_dbid))

    # noinspection PyTypeChecker
    def test_fail_for_invalid_info(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            with self.assertRaises(TypeError):
                rundb.update_dependencies(0, info_by_encoded_path={
                    dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (True, 1)
                })
            with self.assertRaises(TypeError):
                rundb.update_dependencies(0, info_by_encoded_path={
                    dlb.ex.rundb.encode_path(dlb.fs.Path('a')): 1
                })


class ReplaceAndGetDomainInputsTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_is_correct_after_success(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't', b'i0')
            rundb.update_dependencies(tool_dbid1, memo_digest_by_domain={'a': b'A', 'b': b'BB'})
            self.assertEqual({'a': b'A', 'b': b'BB'}, rundb.get_domain_inputs(tool_dbid1))

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_dependencies(tool_dbid2, memo_digest_by_domain={'c': b'CCC'})

            self.assertEqual({'a': b'A', 'b': b'BB'}, rundb.get_domain_inputs(tool_dbid1))  # unchanged
            rundb.update_dependencies(tool_dbid1, memo_digest_by_domain={'a': b'!'})
            self.assertEqual({'a': b'!'}, rundb.get_domain_inputs(tool_dbid1))  # 'b' is removed

            self.assertEqual({'c': b'CCC'}, rundb.get_domain_inputs(tool_dbid2))

    def test_is_unchanged_after_fail(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', b'i1')

            rundb.update_dependencies(tool_dbid, memo_digest_by_domain={'a': b'A', 'b': b'BB'})
            self.assertEqual({'a': b'A', 'b': b'BB'}, rundb.get_domain_inputs(tool_dbid))

            info_by_encoded_path = collections.OrderedDict([
                ('a', b'A!'),  # valid
                (None, 1)   # invalid
            ])
            with self.assertRaises(TypeError):
                rundb.update_dependencies(tool_dbid, memo_digest_by_domain=info_by_encoded_path)

            self.assertEqual({'a': b'A', 'b': b'BB'}, rundb.get_domain_inputs(tool_dbid))  # unchanged

    # noinspection PyTypeChecker
    def test_fails_for_invalid_domain(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            with self.assertRaises(TypeError):
                rundb.update_dependencies(0, memo_digest_by_domain={1: b''})
            with self.assertRaises(ValueError):
                rundb.update_dependencies(0, memo_digest_by_domain={'': b''})
            with self.assertRaises(TypeError):
                rundb.update_dependencies(0, memo_digest_by_domain={'d': 1})


class CleanupTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_scenario1(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            tool_dbid0 = rundb.get_and_register_tool_instance_dbid(b't', b'i0')

            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_dependencies(tool_dbid1, info_by_encoded_path={
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'1'),
                dlb.ex.rundb.encode_path(dlb.fs.Path('b')): (False, b'2')
            })

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't', b'i2')
            rundb.update_dependencies(tool_dbid2, info_by_encoded_path={
                dlb.ex.rundb.encode_path(dlb.fs.Path('c')): (False, b'3')
            })

            self.assertEqual(3, rundb.get_tool_instance_dbid_count())

            rundb.cleanup()

            self.assertEqual(dict(), rundb.get_fsobject_inputs(tool_dbid0))
            self.assertEqual(2, len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(1, len(rundb.get_fsobject_inputs(tool_dbid2)))

            self.assertEqual(3 - 1, rundb.get_tool_instance_dbid_count())

    def test_scenario2(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            rundb.get_and_register_tool_instance_dbid(b't', b'i0')

            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_dependencies(tool_dbid1, info_by_encoded_path={
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'1')
            })
            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't', b'i2')
            rundb.update_dependencies(tool_dbid2, memo_digest_by_domain={'a': b'A'})

            self.assertEqual(3, rundb.get_tool_instance_dbid_count())

            rundb.cleanup()

            self.assertEqual(1, len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(0, len(rundb.get_domain_inputs(tool_dbid1)))
            self.assertEqual(0, len(rundb.get_fsobject_inputs(tool_dbid2)))
            self.assertEqual(1, len(rundb.get_domain_inputs(tool_dbid2)))

            self.assertEqual(3 - 1, rundb.get_tool_instance_dbid_count())


class ForgetRunsBeforeTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_forgets_run_and_dependencies(self):
        t0 = datetime.datetime.utcnow()

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            rundb.get_and_register_tool_instance_dbid(b't', b'i0')

            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_dependencies(tool_dbid1, info_by_encoded_path={
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'1')
            })

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't', b'i2')
            rundb.update_dependencies(tool_dbid2, memo_digest_by_domain={'a': b'A'})
            rundb.commit()

            self.assertEqual(1, len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(1, len(rundb.get_domain_inputs(tool_dbid2)))

        t1 = datetime.datetime.utcnow()

        max_age = t1 - t0 + datetime.timedelta(seconds=1)
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite', max_dependency_age=max_age)) as rundb:
            self.assertEqual(1, len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(1, len(rundb.get_domain_inputs(tool_dbid2)))

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite', max_dependency_age=t1 - t0)) as rundb:
            self.assertEqual(0, len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(0, len(rundb.get_domain_inputs(tool_dbid2)))


class RunSummaryTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_scenario1(self):

        t0 = datetime.datetime.utcnow()

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            rundb.update_run_summary(0, 0)
            self.assertEqual([], rundb.get_latest_successful_run_summaries(10))
            rundb.commit()

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            rundb.update_run_summary(1, 0)
            rundb.commit()

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            rundb.commit()

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            start_datetime, duration_ns, run_count, redo_count = rundb.update_run_summary(2, 3)
            rundb.commit()
            self.assertIsInstance(start_datetime, datetime.datetime)
            self.assertGreater(duration_ns, 0)
            self.assertEqual(2 + 3, run_count)
            self.assertEqual(3, redo_count)

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            summaries10 = rundb.get_latest_successful_run_summaries(10)
            self.assertEqual(3, len(summaries10))

        self.assertEqual([(0, 0), (1, 0), (5, 3)], [t[2:] for t in summaries10])
        for t, _, _, _ in summaries10:
            self.assertGreaterEqual(t, t0, repr(t))

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            summaries1 = rundb.get_latest_successful_run_summaries(1)
            self.assertEqual(1, len(summaries1))
            self.assertEqual(summaries10[-1], summaries1[0])

    def test_too_large_counts_are_limited(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            rundb.update_run_summary(2**100, 2**100)
            rundb.commit()

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            summary = rundb.get_latest_successful_run_summaries(1)[0]
            self.assertEqual(2 * (2**63 - 1), summary[2])
            self.assertEqual(2**63 - 1, summary[3])
