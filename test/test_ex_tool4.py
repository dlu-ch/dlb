# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.di
import dlb.ex
import dlb.ex.tool
import unittest


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

    def redo(self, result, context):
        dlb.di.inform("redoing right now")

        with (context.root_path / self.object_file).native.raw.open('xb'):
            pass

        result.included_files = [dlb.fs.Path('src/a.h'), dlb.fs.Path('src/b.h')]


class RedoResultBeforeRedoTest(unittest.TestCase):

    def test_refers_explicit_dependencies_of_tool_instance(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex.tool._RedoResult(t)
        self.assertEqual(t.source_file, result.source_file)
        self.assertEqual(t.object_file, result.object_file)

    def test_nonexplicit_dependencies_are_notimplemented(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex.tool._RedoResult(t)
        self.assertEqual(NotImplemented, result.included_files)

    def test_fails_on_nondependency(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex.tool._RedoResult(t)

        with self.assertRaises(AttributeError) as cm:
            result._xy
        msg = "'_xy' is not a dependency"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            result.xyz
        msg = "'xyz' is not a dependency"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            result.run()
        msg = "'run' is not a dependency"
        self.assertEqual(msg, str(cm.exception))


class RedoResultAssignmentTest(unittest.TestCase):

    def test_assignment_validates(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex.tool._RedoResult(t)
        result.included_files = ['c.h', 'd.h']
        self.assertEqual((dlb.fs.Path('c.h'), dlb.fs.Path('d.h')), result.included_files)

    def test_fails_to_nondependency(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex.tool._RedoResult(t)
        with self.assertRaises(AttributeError) as cm:
            result.redo = 42
        msg = "'redo' is not a dependency"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_to_already_assigned(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex.tool._RedoResult(t)
        result.included_files = ['c.h', 'd.h']
        with self.assertRaises(AttributeError) as cm:
            result.included_files = ['c.h', 'd.h']
        msg = "'included_files' is already assigned"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_to_explicit(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex.tool._RedoResult(t)
        with self.assertRaises(AttributeError) as cm:
            result.source_file = 'b.cpp'
        msg = "'source_file' is not a non-explicit dependency"
        self.assertEqual(msg, str(cm.exception))
