# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex.rundb
import contextlib
import sqlite3
import unittest
import tools_for_test


class CreationTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_file_exists_after_construction(self):
        with contextlib.closing(dlb.ex.rundb.Database(':memory:')):
            os.path.isfile('./:memory:')

    def test_can_be_constructed_multiple_times(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')):
            pass

        os.path.isfile('./runs.sqlite')

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')):
            pass


class ToolInstanceDbidTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_is_created_as_needed(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't1', 'ti1')
            self.assertIsInstance(tool_dbid1, int)

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't1', 'ti2')
            self.assertNotEqual(tool_dbid2, tool_dbid1)

            tool_dbid3 = rundb.get_and_register_tool_instance_dbid(b't2', 'ti1')
            self.assertNotEqual(tool_dbid3, tool_dbid1)
            self.assertNotEqual(tool_dbid3, tool_dbid2)

    def test_returns_same_of_called_more_than_once(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't1', 'ti1')
            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't1', 'ti1')
            self.assertEqual(tool_dbid2, tool_dbid1)


class BuildFsobjectDbidTest(unittest.TestCase):

    def test_is_str(self):
        self.assertIsInstance(dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('.')), str)

    def test_is_correct(self):
        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a'))
        self.assertEqual('a/', fsobject_dbid)

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a/'))
        self.assertEqual('a/', fsobject_dbid)

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('./a/b/c/../'))
        self.assertTrue(dlb.ex.rundb.is_fsobject_dbid(fsobject_dbid))

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('.'))
        self.assertEqual('', fsobject_dbid)

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('..'))
        self.assertEqual('../', fsobject_dbid)

    def test_is_valid(self):
        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a'))
        self.assertTrue(dlb.ex.rundb.is_fsobject_dbid(fsobject_dbid))

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('./a/b/c/../'))
        self.assertTrue(dlb.ex.rundb.is_fsobject_dbid(fsobject_dbid))

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('.'))
        self.assertTrue(dlb.ex.rundb.is_fsobject_dbid(fsobject_dbid))

    def test_root_is_prefix_of_all(self):
        fsobject_dbid_root = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('.'))
        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a'))
        self.assertTrue(fsobject_dbid.startswith(fsobject_dbid_root))

    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError):
            dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('/a/b'))


class UpdateAndGetFsobjectInputTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_non_existing_is_added(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', 'i')

            fsobject_dbid1 = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a/b/c'))
            rundb.update_fsobject_input(tool_dbid, fsobject_dbid1, False, b'?')

            fsobject_dbid2 = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a/b/'))
            rundb.update_fsobject_input(tool_dbid, fsobject_dbid2, True, None)

            rows = rundb.get_fsobject_inputs(tool_dbid)
            self.assertEqual({fsobject_dbid1: (False, b'?'), fsobject_dbid2: (True, None)}, rows)

            rows = rundb.get_fsobject_inputs(tool_dbid, False)
            self.assertEqual({fsobject_dbid1: (False, b'?')}, rows)

            rows = rundb.get_fsobject_inputs(tool_dbid, True)
            self.assertEqual({fsobject_dbid2: (True, None)}, rows)

    def test_existing_is_replaced(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            tool_dbid = rundb.get_and_register_tool_instance_dbid(b't', 'i')

            fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a/b/c'))
            rundb.update_fsobject_input(tool_dbid, fsobject_dbid, True, b'1')
            rundb.update_fsobject_input(tool_dbid, fsobject_dbid, False, b'234')

            rows = rundb.get_fsobject_inputs(tool_dbid)
            self.assertEqual({fsobject_dbid: (False, b'234')}, rows)

    def test_fails_if_tool_dbid_does_no_exist(self):
        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:
            with self.assertRaises(sqlite3.Error):
                fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a/b/c'))
                rundb.update_fsobject_input(12, fsobject_dbid, True, b'')


class DeclareFsobjectInputAsModifiedTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_scenario1(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            # 1. insert explicit and non-explicit input dependencies for different tool instances

            modified_fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a/b'))

            fsobject_dbids = [
                dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path(s))
                for s in [
                    '.',
                    'c/a/b',
                    'a/b_',
                    'a/B',
                    
                    # these have modified_fsobject_dbid as prefix:
                    'a/b',
                    'a/b/c42',
                    'a/b/c/d',
                    'a/b/c/d/e'
                ]
            ]
            
            fsobject_dbids1_explicit = [
                fsobject_dbids[1],
                fsobject_dbids[3],
                fsobject_dbids[5]   # *+
            ]
            fsobject_dbids1_nonexplicit = [
                fsobject_dbids[0],
                fsobject_dbids[2],
                fsobject_dbids[4],  # *+
                fsobject_dbids[6],  # *
            ]
            self.assertEqual(set(), set(fsobject_dbids1_explicit) & set(fsobject_dbids1_nonexplicit))

            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't', 'i1')
            for dbid in fsobject_dbids1_explicit:
                rundb.update_fsobject_input(tool_dbid1, dbid, True, b'e1')
            for dbid in fsobject_dbids1_nonexplicit:
                rundb.update_fsobject_input(tool_dbid1, dbid, False, b'n1')

            fsobject_dbids2_explicit = [
                fsobject_dbids[0],
                fsobject_dbids[2],  
                fsobject_dbids[3],
                fsobject_dbids[5]   # *
            ]
            fsobject_dbids2_nonexplicit = [
                fsobject_dbids[1],
                fsobject_dbids[6],  # *
            ]
            self.assertEqual(set(), set(fsobject_dbids2_explicit) & set(fsobject_dbids2_nonexplicit))

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't', 'i2')
            for dbid in fsobject_dbids2_explicit:
                rundb.update_fsobject_input(tool_dbid2, dbid, True, b'e2')
            for dbid in fsobject_dbids2_nonexplicit:
                rundb.update_fsobject_input(tool_dbid2, dbid, False, b'n2')

            self.assertEqual(len(fsobject_dbids1_explicit) + len(fsobject_dbids1_nonexplicit),
                             len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(len(fsobject_dbids2_explicit) + len(fsobject_dbids2_nonexplicit),
                             len(rundb.get_fsobject_inputs(tool_dbid2)))

            # 2.1 define some as modified

            rundb.declare_fsobject_input_as_modified(modified_fsobject_dbid)

            # 2.2 check result

            fsobjects_dbid1 = rundb.get_fsobject_inputs(tool_dbid1)
            self.assertEqual({
                fsobject_dbids[0]: (False, b'n1'),
                fsobject_dbids[1]: (True,  b'e1'),
                fsobject_dbids[2]: (False, b'n1'),
                fsobject_dbids[3]: (True,  b'e1'),
                fsobject_dbids[4]: (False, None),
                fsobject_dbids[6]: (False, None)
            }, fsobjects_dbid1)

            fsobjects_dbid2 = rundb.get_fsobject_inputs(tool_dbid2)
            self.assertEqual({
                fsobject_dbids[0]: (True,  b'e2'),
                fsobject_dbids[1]: (False, b'n2'),
                fsobject_dbids[2]: (True,  b'e2'),
                fsobject_dbids[3]: (True,  b'e2'),
                fsobject_dbids[6]: (False, None)
            }, fsobjects_dbid2)

            # 3.1 define _all_ as modified

            rundb.declare_fsobject_input_as_modified(fsobject_dbids[0])  # managed tree's root...

            # 3.2 check result

            fsobjects_dbid1 = rundb.get_fsobject_inputs(tool_dbid1)
            self.assertEqual({
                fsobject_dbids[0]: (False, None),
                fsobject_dbids[2]: (False, None),
                fsobject_dbids[4]: (False, None),
                fsobject_dbids[6]: (False, None)
            }, fsobjects_dbid1)

            fsobjects_dbid2 = rundb.get_fsobject_inputs(tool_dbid2)
            self.assertEqual({
                fsobject_dbids[1]: (False, None),
                fsobject_dbids[6]: (False, None)
            }, fsobjects_dbid2)

class CleanupTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_scenario1(self):

        with contextlib.closing(dlb.ex.rundb.Database('runs.sqlite')) as rundb:

            tool_dbid0 = rundb.get_and_register_tool_instance_dbid(b't', 'i0')

            tool_dbid1 = rundb.get_and_register_tool_instance_dbid(b't', 'i1')
            rundb.update_fsobject_input(tool_dbid1, dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a')), False, b'1')
            rundb.update_fsobject_input(tool_dbid1, dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('b')), False, b'2')

            tool_dbid2 = rundb.get_and_register_tool_instance_dbid(b't', 'i2')
            rundb.update_fsobject_input(tool_dbid2, dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('c')), False, b'3')

            self.assertEqual(3, rundb.get_tool_instance_dbid_count())

            rundb.cleanup()

            self.assertEqual(dict(), rundb.get_fsobject_inputs(tool_dbid0))
            self.assertEqual(2, len(rundb.get_fsobject_inputs(tool_dbid1)))
            self.assertEqual(1, len(rundb.get_fsobject_inputs(tool_dbid2)))

            self.assertEqual(3 - 1, rundb.get_tool_instance_dbid_count())
