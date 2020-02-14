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
        self.assertEqual('/', fsobject_dbid)

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('..'))
        self.assertEqual('../', fsobject_dbid)

    def test_is_valid(self):
        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('a'))
        self.assertTrue(dlb.ex.rundb.is_fsobject_dbid(fsobject_dbid))

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('./a/b/c/../'))
        self.assertTrue(dlb.ex.rundb.is_fsobject_dbid(fsobject_dbid))

        fsobject_dbid = dlb.ex.rundb.build_fsobject_dbid(dlb.fs.Path('.'))
        self.assertTrue(dlb.ex.rundb.is_fsobject_dbid(fsobject_dbid))

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
