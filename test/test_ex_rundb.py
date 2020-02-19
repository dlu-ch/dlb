# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex.rundb
import collections
import contextlib
import unittest
import tools_for_test


class CreationTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_file_exists_after_construction(self):
        with contextlib.closing(dlb.ex.rundb.Database(':memory:')):
            os.path.isfile(':memory:')

    def test_can_be_constructed_multiple_times(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')):
            pass

        os.path.isfile('runs.sqlite')

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')):
            pass

    def test_fails_with_meaningful_message_on_permission_problem_when_nonexisting(self):
        os.mkdir('t')
        os.chmod('t', 0x000)
        try:
            regex = (
                r"(?m)\A"
                r"could not open non-existing run-database: '.+'\n"
                r"  \| reason: sqlite3.OperationalError: unable to open database file\n"
                r"  \| check access permissions\Z"
            )
            with self.assertRaisesRegex(dlb.ex.rundb.DatabaseError, regex):
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

    def test_isdir_is_correct(self):
        self.assertFalse(dlb.ex.rundb.decode_encoded_path(dlb.ex.rundb.encode_path(dlb.fs.Path('a/b')), is_dir=False).is_dir())
        self.assertTrue(dlb.ex.rundb.decode_encoded_path(dlb.ex.rundb.encode_path(dlb.fs.Path('a/b')), is_dir=True).is_dir())
        self.assertTrue(dlb.ex.rundb.decode_encoded_path(dlb.ex.rundb.encode_path(dlb.fs.Path('.')), is_dir=False).is_dir())


class UpdateAndGetFsobjectInputTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_non_existing_is_added(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', b'i')

            encoded_path1 = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/c'))
            rundb.update_fsobject_input(tool_dbid, encoded_path1, False, b'?')

            encoded_path2 = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/'))
            rundb.update_fsobject_input(tool_dbid, encoded_path2, True, None)

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
            rundb.update_fsobject_input(tool_dbid, encoded_path, True, b'1')
            rundb.update_fsobject_input(tool_dbid, encoded_path, False, b'234')

            rows = rundb.get_fsobject_inputs(tool_dbid)
            self.assertEqual({encoded_path: (False, b'234')}, rows)

    def test_fails_if_tool_dbid_does_no_exist(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            with self.assertRaises(dlb.ex.rundb.DatabaseError):
                encoded_path = dlb.ex.rundb.encode_path(dlb.fs.Path('a/b/c'))
                rundb.update_fsobject_input(12, encoded_path, True, b'')

    def test_update_fails_for_invalid_encoded_path(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            with self.assertRaises(ValueError):
                # noinspection PyTypeChecker
                rundb.update_fsobject_input(12, 3, True, b'')
            with self.assertRaises(ValueError):
                rundb.update_fsobject_input(12, '/3', True, b'')


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
            for dbid in encoded_paths1_explicit:
                rundb.update_fsobject_input(tool_dbid1, dbid, True, b'e1')
            for dbid in encoded_paths1_nonexplicit:
                rundb.update_fsobject_input(tool_dbid1, dbid, False, b'n1')

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
            for dbid in encoded_paths2_explicit:
                rundb.update_fsobject_input(tool_dbid2, dbid, True, b'e2')
            for dbid in encoded_paths2_nonexplicit:
                rundb.update_fsobject_input(tool_dbid2, dbid, False, b'n2')

            self.assertEqual(len(encoded_paths1_explicit) + len(encoded_paths1_nonexplicit),
                             len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(len(encoded_paths2_explicit) + len(encoded_paths2_nonexplicit),
                             len(rundb.get_fsobject_inputs(tool_dbid2)))

            # 2.1 define some as modified

            rundb.declare_fsobject_input_as_modified(modified_encoded_path)

            # 2.2 check result

            encoded_paths1 = rundb.get_fsobject_inputs(tool_dbid1)
            self.assertEqual({
                encoded_paths[0]: (False, b'n1'),
                encoded_paths[1]: (True,  b'e1'),
                encoded_paths[2]: (False, b'n1'),
                encoded_paths[3]: (True,  b'e1'),
                encoded_paths[4]: (False, None),
                encoded_paths[6]: (False, None)
            }, encoded_paths1)

            encoded_paths2 = rundb.get_fsobject_inputs(tool_dbid2)
            self.assertEqual({
                encoded_paths[0]: (True,  b'e2'),
                encoded_paths[1]: (False, b'n2'),
                encoded_paths[2]: (True,  b'e2'),
                encoded_paths[3]: (True,  b'e2'),
                encoded_paths[6]: (False, None)
            }, encoded_paths2)

            # 3.1 define _all_ as modified

            rundb.declare_fsobject_input_as_modified(encoded_paths[0])  # managed tree's root...

            # 3.2 check result

            encoded_paths1 = rundb.get_fsobject_inputs(tool_dbid1)
            self.assertEqual({
                encoded_paths[0]: (False, None),
                encoded_paths[2]: (False, None),
                encoded_paths[4]: (False, None),
                encoded_paths[6]: (False, None)
            }, encoded_paths1)

            encoded_paths2 = rundb.get_fsobject_inputs(tool_dbid2)
            self.assertEqual({
                encoded_paths[1]: (False, None),
                encoded_paths[6]: (False, None)
            }, encoded_paths2)


class ReplaceFsobjectInputsTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_is_correct_after_success(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            tool_dbid0 = rundb.get_and_register_tool_instance_dbid(b't', b'i0')
            rundb.update_fsobject_input(tool_dbid0, dlb.ex.rundb.encode_path(dlb.fs.Path('a')), False, b'0')

            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_fsobject_input(tool_dbid, dlb.ex.rundb.encode_path(dlb.fs.Path('a')), False, b'1')
            rundb.update_fsobject_input(tool_dbid, dlb.ex.rundb.encode_path(dlb.fs.Path('b')), False, b'1')

            info_by_by_encoded_path = {
                dlb.ex.rundb.encode_path(dlb.fs.Path('b')): (True, b'3'),
                dlb.ex.rundb.encode_path(dlb.fs.Path('c')): (False, b'4')
            }
            rundb.replace_fsobject_inputs(tool_dbid, info_by_by_encoded_path)

            self.assertEqual(info_by_by_encoded_path, rundb.get_fsobject_inputs(tool_dbid))
            self.assertEqual({
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'0')
            }, rundb.get_fsobject_inputs(tool_dbid0)) # input dependencies of tool_dbid0 are unchanged

    def test_is_changed_after_fail(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_fsobject_input(tool_dbid, dlb.ex.rundb.encode_path(dlb.fs.Path('a')), False, b'1')
            rundb.update_fsobject_input(tool_dbid, dlb.ex.rundb.encode_path(dlb.fs.Path('b')), False, b'1')

            info_by_by_encoded_path = collections.OrderedDict([
                (dlb.ex.rundb.encode_path(dlb.fs.Path('b')), (True, b'3')),
                (None, (False, b'4'))
            ])
            with self.assertRaises(ValueError):
                rundb.replace_fsobject_inputs(tool_dbid, info_by_by_encoded_path)

            self.assertEqual({
                dlb.ex.rundb.encode_path(dlb.fs.Path('a')): (False, b'1'),
                dlb.ex.rundb.encode_path(dlb.fs.Path('b')): (False, b'1')
            }, rundb.get_fsobject_inputs(tool_dbid))


class CleanupTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_scenario1(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            tool_dbid0 = rundb.get_and_register_tool_instance_dbid(b't', b'i0')

            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't', b'i1')
            rundb.update_fsobject_input(tool_dbid1, dlb.ex.rundb.encode_path(dlb.fs.Path('a')), False, b'1')
            rundb.update_fsobject_input(tool_dbid1, dlb.ex.rundb.encode_path(dlb.fs.Path('b')), False, b'2')

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't', b'i2')
            rundb.update_fsobject_input(tool_dbid2, dlb.ex.rundb.encode_path(dlb.fs.Path('c')), False, b'3')

            self.assertEqual(3, rundb.get_tool_instance_dbid_count())

            rundb.cleanup()

            self.assertEqual(dict(), rundb.get_fsobject_inputs(tool_dbid0))
            self.assertEqual(2, len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(1, len(rundb.get_fsobject_inputs(tool_dbid2)))

            self.assertEqual(3 - 1, rundb.get_tool_instance_dbid_count())
