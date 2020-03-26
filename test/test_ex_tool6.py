# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.di
import dlb.ex
import io
import asyncio
import unittest
import tools_for_test


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

    async def redo(self, result, context):
        dlb.di.inform(f"redoing right now for {self.object_file.as_string()}")

        await asyncio.sleep(0.5)

        dlb.di.inform(f"create {self.object_file.as_string()}")

        with (context.root_path / self.object_file).native.raw.open('xb'):
             pass

        result.included_files = [dlb.fs.Path('a.h'), dlb.fs.Path('b.h')]


class BTool(dlb.ex.Tool):
    async def redo(self, result, context):
        pass


class IsCompleteTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_non_result(self):
        msg = "'result' is not a result of dlb.ex.Tool.run()"

        with self.assertRaises(TypeError) as cm:
            dlb.ex.is_complete(None)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            dlb.ex.is_complete(27)
        self.assertEqual(msg, str(cm.exception))

    def test_true_if_no_redo(self):

        with dlb.ex.Context():
            BTool().run()
            r = BTool().run()
            self.assertFalse(r)
            self.assertTrue(dlb.ex.is_complete(r))

    def test_false_if_incomplete_redo(self):

        with dlb.ex.Context():
            r = BTool().run()
            self.assertTrue(r)
            self.assertFalse(dlb.ex.is_complete(r))
        self.assertTrue(dlb.ex.is_complete(r))


class MultiplePendingRedosTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def setUp(self):
        super().setUp()
        open('a.cpp', 'xb').close()
        open('b.cpp', 'xb').close()

    def test_one_pending_redos(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.ex.Context():
            self.assertEqual(1, dlb.ex.Context.max_parallel_redo_count)
            ra = ATool(source_file='a.cpp', object_file='a.o').run()
            rb = ATool(source_file='b.cpp', object_file='b.o').run()
            self.assertIsNotNone(ra)
            self.assertIsNotNone(rb)
            self.assertFalse(dlb.ex.is_complete(ra))  # but not yet consumed
            self.assertFalse(dlb.ex.is_complete(rb))

        regex = (
            r"(?m)"
            r"I create a.o\n"
            r"(.|\n)*"
            r"I redoing right now for b.o\n"
        )
        self.assertRegex(output.getvalue(), regex)

    def test_two_pending_redos(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.ex.Context(max_parallel_redo_count=2):
            self.assertEqual(2, dlb.ex.Context.max_parallel_redo_count)
            ra = ATool(source_file='a.cpp', object_file='a.o').run()
            rb = ATool(source_file='b.cpp', object_file='b.o').run()
            self.assertIsNotNone(ra)
            self.assertIsNotNone(rb)
            self.assertFalse(dlb.ex.is_complete(ra))
            self.assertFalse(dlb.ex.is_complete(rb))

            with dlb.ex.Context():
                self.assertEqual(1, dlb.ex.Context.max_parallel_redo_count)

        regex = (
            r"(?m)"
            r"I redoing right now for b.o\n"
            r"I create a.o\n"  # _after_ b.o
        )
        self.assertRegex(output.getvalue(), regex)

    def test_inner_context_completes_redo(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.ex.Context(max_parallel_redo_count=2):
            self.assertEqual(2, dlb.ex.Context.max_parallel_redo_count)
            ra = ATool(source_file='a.cpp', object_file='a.o').run()
            self.assertIsNotNone(ra)
            self.assertFalse(dlb.ex.is_complete(ra))

            with dlb.ex.Context(max_parallel_redo_count=200):
                pass

            self.assertTrue(dlb.ex.is_complete(ra))
            rb = ATool(source_file='b.cpp', object_file='b.o').run()
            self.assertIsNotNone(rb)
            self.assertFalse(dlb.ex.is_complete(rb))

        regex = (
            r"(?m)"
            r"I create a.o\n"
            r"(.|\n)*"
            r"I redoing right now for b.o\n"
        )
        self.assertRegex(output.getvalue(), regex)

    def test_env_modification_completes_redo(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.ex.Context(max_parallel_redo_count=2):
            self.assertEqual(2, dlb.ex.Context.max_parallel_redo_count)
            ra = ATool(source_file='a.cpp', object_file='a.o').run()
            self.assertIsNotNone(ra)
            self.assertFalse(dlb.ex.is_complete(ra))

            dlb.ex.Context.active.env.import_from_outer('LANG', restriction=r'.*', example='')

            self.assertTrue(dlb.ex.is_complete(ra))
            rb = ATool(source_file='b.cpp', object_file='b.o').run()
            self.assertIsNotNone(rb)
            self.assertFalse(dlb.ex.is_complete(rb))

        regex = (
            r"(?m)"
            r"I create a.o\n"
            r"(.|\n)*"
            r"I redoing right now for b.o\n"
        )
        self.assertRegex(output.getvalue(), regex)

    def test_helper_modification_completes_redo(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.ex.Context(max_parallel_redo_count=2):
            self.assertEqual(2, dlb.ex.Context.max_parallel_redo_count)
            ra = ATool(source_file='a.cpp', object_file='a.o').run()
            self.assertIsNotNone(ra)
            self.assertFalse(dlb.ex.is_complete(ra))

            dlb.ex.Context.active.helper['a'] = '/a'

            self.assertTrue(dlb.ex.is_complete(ra))
            rb = ATool(source_file='b.cpp', object_file='b.o').run()
            self.assertIsNotNone(rb)
            self.assertFalse(dlb.ex.is_complete(rb))

        regex = (
            r"(?m)"
            r"I create a.o\n"
            r"(.|\n)*"
            r"I redoing right now for b.o\n"
        )
        self.assertRegex(output.getvalue(), regex)


class KeyboardInterruptTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    class CTool(dlb.ex.Tool):
        async def redo(self, result, context):
            raise KeyboardInterrupt

    def test_does_recover(self):
        try:
            with dlb.ex.Context():
                with dlb.ex.Context():
                    KeyboardInterruptTest.CTool().run()
        except KeyboardInterrupt:
            pass

        with dlb.ex.Context():
            pass

    def test_does_recover2(self):
        try:
            with dlb.ex.Context():
                with dlb.ex.Context(max_parallel_redo_count=2):
                    KeyboardInterruptTest.CTool().run()
                    KeyboardInterruptTest.CTool().run()
        except KeyboardInterrupt:
            pass

        with dlb.ex.Context():
            pass


class ContextInRedoTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_context_in_redo(self):

        class CTool(dlb.ex.Tool):
            async def redo(self, result, context):
                with dlb.ex.Context():
                    pass

        with self.assertRaises(RuntimeError):
            with dlb.ex.Context():
                CTool().run()

    def test_fails_for_env_modification_in_redo(self):
        class CTool(dlb.ex.Tool):
            async def redo(self, result, context):
                dlb.ex.Context.active.env.import_from_outer('a', restriction=r'.*', example='')

        with self.assertRaises(RuntimeError):
            with dlb.ex.Context():
                CTool().run()

    def test_fails_for_helper_modification_in_redo(self):
        class CTool(dlb.ex.Tool):
            async def redo(self, result, context):
                dlb.ex.Context.active.helper['a'] = 'A'

        with self.assertRaises(RuntimeError):
            with dlb.ex.Context():
                CTool().run()
