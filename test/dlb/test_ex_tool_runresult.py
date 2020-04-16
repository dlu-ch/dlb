# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.di
import dlb.ex
import dlb.ex._tool
import unittest


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.input.RegularFile()
    object_file = dlb.ex.output.RegularFile()
    included_files = dlb.ex.input.RegularFile[:](explicit=False)

    async def redo(self, result, context):
        dlb.di.inform("redoing right now")

        with (context.root_path / self.object_file).native.raw.open('xb'):
            pass

        result.included_files = [dlb.fs.Path('src/a.h'), dlb.fs.Path('src/b.h')]


class WithoutRedoBeforeRedoTest(unittest.TestCase):

    def test_is_true(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        self.assertFalse(dlb.ex._tool._RunResult(t, False))

    def test_assignment_fails(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, False)
        with self.assertRaises(AttributeError):
            result.source_file = 'b.cpp'


class WithRedoBeforeRedoTest(unittest.TestCase):

    def test_is_true(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        self.assertTrue(dlb.ex._tool._RunResult(t, True))

    def test_refers_explicit_dependencies_of_tool_instance(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)
        self.assertEqual(t.source_file, result.source_file)
        self.assertEqual(t.object_file, result.object_file)

    def test_nonexplicit_dependencies_are_notimplemented(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)
        self.assertEqual(NotImplemented, result.included_files)

    def test_fails_on_nondependency(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)

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


class AssignmentTest(unittest.TestCase):

    def test_assignment_validates(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)
        result.included_files = ['c.h', 'd.h']
        self.assertEqual((dlb.fs.Path('c.h'), dlb.fs.Path('d.h')), result.included_files)

    def test_fails_to_nondependency(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)
        with self.assertRaises(AttributeError) as cm:
            result.redo = 42
        msg = "'redo' is not a dependency"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_to_already_assigned(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)
        result.included_files = ['c.h', 'd.h']
        with self.assertRaises(AttributeError) as cm:
            result.included_files = ['c.h', 'd.h']
        msg = "'included_files' is already assigned"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_to_explicit(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)
        with self.assertRaises(AttributeError) as cm:
            result.source_file = 'b.cpp'
        msg = "'source_file' is not a non-explicit dependency"
        self.assertEqual(msg, str(cm.exception))


class Repr(unittest.TestCase):

    def test_shows_explicit_without_redo(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, False)
        self.assertEqual("RunResult(source_file=Path('a.cpp'), object_file=Path('a.o'))", repr(result))

    def test_shows_explicit_and_assigned_with_redo(self):
        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)
        self.assertEqual("RunResult(source_file=Path('a.cpp'), object_file=Path('a.o'))", repr(result))

        t = ATool(source_file='a.cpp', object_file='a.o')
        result = dlb.ex._tool._RunResult(t, True)
        result.included_files = ['i.h']
        s = "RunResult(included_files=(Path('i.h'),), source_file=Path('a.cpp'), object_file=Path('a.o'))"
        self.assertEqual(s, repr(result))
