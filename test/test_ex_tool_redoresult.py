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


class ResultAssignmentTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_redo_that_does_not_assign_required_input(self):
        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                pass

        t = CTool(object_file='a.o')
        with self.assertRaises(dlb.ex.RedoError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "non-explicit dependency not assigned during redo: 'included_files'\n"
            "  | use 'result.included_files = ...' in body of redo(self, result, context)"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_redo_that_does_not_assign_required_output(self):
        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            log_file = dlb.ex.Tool.Output.RegularFile(explicit=False)

            async def redo(self, result, context):
                pass

        t = CTool(object_file='a.o')
        with self.assertRaises(dlb.ex.RedoError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "non-explicit dependency not assigned during redo: 'log_file'\n"
            "  | use 'result.log_file = ...' in body of redo(self, result, context)"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_if_input_dependency_if_relative_and_not_in_managed_tree(self):
        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                result.included_files = ['a/../b']

        t = CTool(object_file='a.o')
        with self.assertRaises(dlb.ex.RedoError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "non-explicit input dependency 'included_files' contains a relative path "
            "that is not a managed tree path: 'a/../b'"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_if_output_dependency_not_in_managed_tree(self):
        class CTool(dlb.ex.Tool):
            log_file = dlb.ex.Tool.Output.RegularFile(explicit=False)

            async def redo(self, result, context):
                result.log_file = '/tmp/x'

        t = CTool()
        with self.assertRaises(dlb.ex.RedoError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "non-explicit output dependency 'log_file' contains a path "
            "that is not a managed tree path: '/tmp/x'"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_if_redo_assigns_none_to_required(self):
        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                result.included_files = None

        t = CTool(object_file='a.o')
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = "value for required dependency must not be None"
        self.assertEqual(msg, str(cm.exception))

    def test_nonrequired_is_none_if_redo_does_not_assign(self):
        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False, required=False)
            log_file = dlb.ex.Tool.Output.RegularFile(explicit=False, required=False)

            # noinspection PyShadowingNames
            async def redo(self, result, context):
                pass

        t = CTool(object_file='a.o')
        with dlb.ex.Context():
            result = t.run()
        self.assertIsNone(result.included_files)
        self.assertIsNone(result.log_file)

    def test_silently_ignores_input_dependency_if_absolute_and_not_in_managed_tree(self):
        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                result.included_files = ['/x/y']

        t = CTool(object_file='a.o')
        with dlb.ex.Context():
            t.run()

    def test_can_assign_output_dependency_in_managed_tree(self):
        class CTool(dlb.ex.Tool):
            log_file = dlb.ex.Tool.Output.RegularFile(explicit=False)

            async def redo(self, result, context):
                result.log_file = 'x'

        t = CTool()
        with dlb.ex.Context():
            r = t.run()
        self.assertEqual(dlb.fs.Path('x'), r.log_file)

    def test_redo_can_assigns_none_to_nonrequired(self):
        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False, required=False)

            # noinspection PyShadowingNames
            async def redo(self, result, context):
                result.included_files = None

        t = CTool(object_file='a.o')
        with dlb.ex.Context():
            result = t.run()
        self.assertIsNone(result.included_files)


class RedoResultEnvVarTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_explicit_envvar_are_assigned_on_tool_instance(self):
        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            language = dlb.ex.Tool.Input.EnvVar(name='LANG',
                                                restriction=r'(?P<language>[a-z]{2})_(?P<territory>[A-Z]{2})',
                                                example='sv_SE')
            cflags = dlb.ex.Tool.Input.EnvVar(name='CFLAGS', restriction='.+', example='-O2', required=False)

            async def redo(self, result, context):
                pass

        t = CTool(object_file='a.o', language='de_CH')
        self.assertEqual({'language': 'de', 'territory': 'CH'}, t.language.groups)
        self.assertIsNone(t.cflags)

        t = CTool(object_file='a.o', language='de_CH', cflags='-Wall')
        self.assertEqual('-Wall', t.cflags.raw)

    def test_nonexplicit_envvar_are_assigned_on_result(self):
        try:
            del os.environ['LANG']
        except KeyError:
            pass

        try:
            del os.environ['CFLAGS']
        except KeyError:
            pass

        class CTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            language = dlb.ex.Tool.Input.EnvVar(name='LANG',
                                                restriction=r'(?P<language>[a-z]{2})_(?P<territory>[A-Z]{2})',
                                                example='sv_SE',
                                                explicit=False)
            cflags = dlb.ex.Tool.Input.EnvVar(name='CFLAGS', restriction='.+', example='-O2',
                                              required=False, explicit=False)

            # noinspection PyShadowingNames
            async def redo(self, result, context):
                pass

        t = CTool(object_file='a.o')
        self.assertIs(NotImplemented, t.language)
        self.assertIs(NotImplemented, t.cflags)

        with dlb.ex.Context() as c:
            c.env.import_from_outer('LANG', restriction='[a-z]{2}_[A-Z]{2}', example='sv_SE')
            c.env['LANG'] = 'de_CH'
            result = t.run()

        self.assertEqual({'language': 'de', 'territory': 'CH'}, result.language.groups)
        self.assertIsNone(result.cflags)

        with dlb.ex.Context() as c:
            c.env.import_from_outer('LANG', restriction='[a-z]{2}_[A-Z]{2}', example='sv_SE')
            with self.assertRaises(dlb.ex.RedoError) as cm:
                t.run()
        msg = (
            "not a defined environment variable in the context: 'LANG'\n"
            "  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...]' = ..."
        )
        self.assertEqual(msg, str(cm.exception))


class RedoResultExplicitInputDependencyTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_absolute_in_managed_tree_remains_absolute(self):
        open('a.cpp', 'xb').close()

        with dlb.ex.Context() as c:
            t = ATool(source_file=c.root_path / 'a.cpp', object_file='a.o')
            r = t.run()
            self.assertEqual(c.root_path / 'a.cpp', r.source_file)

    def test_absolute_can_be_outside_managed_tree(self):
        open('x.cpp', 'xb').close()

        os.mkdir('t')
        with tools_for_test.DirectoryChanger('t'):
            os.mkdir('.dlbroot')
            open('a.cpp', 'xb').close()

            with dlb.ex.Context() as c:
                t = ATool(source_file=c.root_path / '../x.cpp', object_file='a.o')
                t.run()


class RedoResultObjectTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_nonexplicit_object_is_assigned_on_result(self):
        class CTool(dlb.ex.Tool):
            calculated = dlb.ex.Tool.Output.Object(explicit=False)

            async def redo(self, result, context):
                result.calculated = 42

        t = CTool()
        with dlb.ex.Context():
            r = t.run()
            self.assertTrue(r)
            self.assertEqual(42, r.calculated)


class RedoResultRepr(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_result_repr_is_meaningful(self):
        t = ATool(source_file='a.cpp', object_file='a.o')

        open('a.cpp', 'xb').close()

        with dlb.ex.Context():
            r = t.run()
            self.assertTrue(r)
            self.assertFalse(dlb.ex.aseq.is_complete(r))
            imcomplete_repr = repr(r)
        complete_repr = repr(r)

        self.assertEqual("<proxy object for future <class 'dlb.ex.Tool.RunResult'> result>", imcomplete_repr)
        s = (
            "<proxy object for RunResult(included_files=(Path('a.h'), Path('b.h')), source_file=Path('a.cpp'), "
            "object_file=Path('a.o')) result>"
        )
        self.assertEqual(s, complete_repr)
