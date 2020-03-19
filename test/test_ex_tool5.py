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
import dlb.cf
import dlb.ex
import dlb.ex.aseq
import logging
import marshal
import tempfile
import zipfile
import io
import unittest
import tools_for_test


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

    async def redo(self, result, context):
        dlb.di.inform("redoing right now")

        with (context.root_path / self.object_file).native.raw.open('wb'):
             pass

        result.included_files = [dlb.fs.Path('a.h'), dlb.fs.Path('b.h')]


class RunNonExplicitInputDependencyTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_new_or_missing_dependency_causes_redo(self):
        open('a.cpp', 'xb').close()

        t = ATool(source_file='a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.run())

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())  # because new dependency
            regex = (
                r"(?m)\b"
                r"redo necessary because of filesystem object: 'a\.h' \n"
                r" *  \| reason: was a new dependency or was potentially changed by a redo\n"
            )
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.run())

        open('a.h', 'xb').close()

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())  # because new dependency
            regex = (
                r"(?m)\b"
                r"redo necessary because of filesystem object: 'a\.h' \n"
                r" *  \| reason: existence has changed\n"
            )
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.run())

        os.remove('a.h')

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())  # because of new dependency
            regex = (
                r"(?m)\b"
                r"redo necessary because of non-existent filesystem object: 'a.h'\n"
            )
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.run())

    def test_invalid_dependency_causes_redo(self):
        open('a.cpp', 'xb').close()
        open('a.h', 'xb').close()

        t = ATool(source_file='a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertTrue(t.run())  # because of new dependency
            self.assertFalse(t.run())

        with dlb.ex.Context():
            # replace memo by invalid memo
            rundb = dlb.ex.context._get_rundb()
            rundb.update_fsobject_input(1, dlb.ex.rundb.encode_path(dlb.fs.Path('a.h')), False, marshal.dumps(42))

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())  # because new dependency
            regex = (
                r"(?m)\b"
                r"redo necessary because of filesystem object: 'a.h' \n"
                r" *  \| reason: state before last successful redo is unknown\n"
            )
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.run())

        with dlb.ex.Context():
            # add dependency with invalid encoded path
            rundb = dlb.ex.context._get_rundb()
            rundb.update_fsobject_input(1, 'a/../', False, None)

            output = io.StringIO()
            dlb.di.set_output_file(output)
            r = t.run()
            self.assertTrue(r)
            with r:
                pass

            regex = r"\b()redo necessary because of invalid encoded path: 'a/\.\./'\n"
            self.assertRegex(output.getvalue(), regex)
            self.assertNotIn('a/../', rundb.get_fsobject_inputs(1, is_explicit_filter=False))

            self.assertFalse(t.run())

        with dlb.ex.Context():
            # add non-existent dependency with invalid memo
            rundb = dlb.ex.context._get_rundb()
            rundb.update_fsobject_input(1, 'd.h/', False, marshal.dumps(42))

            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            regex = r"\b()redo necessary because of non-existent filesystem object: 'd\.h'\n"
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.run())


class RunNonExplicitInputDependencyChmodTest(tools_for_test.TemporaryDirectoryWithChmodTestCase):

    def test_inaccessible_dependency_causes_redo(self):
        os.mkdir('.dlbroot')
        open('a.cpp', 'xb').close()
        open('a.h', 'xb').close()

        t = ATool(source_file='a.cpp', object_file='a.o')

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertTrue(t.run())  # because of new dependency
            self.assertFalse(t.run())

        os.mkdir('t')
        os.chmod('t', 0o000)

        try:
            with dlb.ex.Context():
                # add inaccessible dependency
                rundb = dlb.ex.context._get_rundb()
                rundb.update_fsobject_input(1, 't/d.h/', False, None)

                output = io.StringIO()
                dlb.di.set_output_file(output)
                self.assertTrue(t.run())
                regex = r"\b()redo necessary because of inaccessible filesystem object: 't/d\.h'\n"
                self.assertRegex(output.getvalue(), regex)
                self.assertFalse(t.run())
        finally:
            os.chmod('t', 0o700)


class RedoTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_redo_that_does_not_assign_required_input(self):
        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                pass

        t = BTool(object_file='a.o')
        with self.assertRaises(dlb.ex.RedoError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "non-explicit dependency not assigned during redo: 'included_files'\n"
            "  | use 'result.included_files = ...' in body of redo(self, result, context)"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_redo_that_does_not_assign_required_output(self):
        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            log_file = dlb.ex.Tool.Output.RegularFile(explicit=False)

            async def redo(self, result, context):
                pass

        t = BTool(object_file='a.o')
        with self.assertRaises(dlb.ex.RedoError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "non-explicit dependency not assigned during redo: 'log_file'\n"
            "  | use 'result.log_file = ...' in body of redo(self, result, context)"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_nonrequired_is_none_if_redo_does_not_assign(self):
        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False, required=False)
            log_file = dlb.ex.Tool.Output.RegularFile(explicit=False, required=False)

            # noinspection PyShadowingNames
            async def redo(self, result, context):
                pass

        t = BTool(object_file='a.o')
        with dlb.ex.Context():
            result = t.run()
        self.assertIsNone(result.included_files)
        self.assertIsNone(result.log_file)

    def test_fails_if_input_dependency_if_relative_and_not_in_managed_tree(self):
        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                result.included_files = ['a/../b']

        t = BTool(object_file='a.o')
        with self.assertRaises(dlb.ex.RedoError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "non-explicit input dependency 'included_files' contains a relative path "
            "that is not a managed tree path: 'a/../b'"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_silently_ignores_input_dependency_if_absolute_and_not_in_managed_tree(self):
        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                result.included_files = ['/x/y']

        t = BTool(object_file='a.o')
        with dlb.ex.Context():
            t.run()

    def test_can_assign_output_dependency_in_managed_tree(self):
        class BTool(dlb.ex.Tool):
            log_file = dlb.ex.Tool.Output.RegularFile(explicit=False)

            async def redo(self, result, context):
                result.log_file = 'x'

        t = BTool()
        with dlb.ex.Context():
            r = t.run()
        self.assertEqual(dlb.fs.Path('x'), r.log_file)

    def test_fails_if_output_dependency_not_in_managed_tree(self):
        class BTool(dlb.ex.Tool):
            log_file = dlb.ex.Tool.Output.RegularFile(explicit=False)

            async def redo(self, result, context):
                result.log_file = '/tmp/x'

        t = BTool()
        with self.assertRaises(dlb.ex.RedoError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = (
            "non-explicit output dependency 'log_file' contains a path "
            "that is not a managed tree path: '/tmp/x'"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_if_redo_assigns_none_to_required(self):
        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                result.included_files = None

        t = BTool(object_file='a.o')
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                t.run()
        msg = "value for required dependency must not be None"
        self.assertEqual(msg, str(cm.exception))

    def test_redo_can_assigns_none_to_nonrequired(self):
        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False, required=False)

            # noinspection PyShadowingNames
            async def redo(self, result, context):
                result.included_files = None

        t = BTool(object_file='a.o')
        with dlb.ex.Context():
            result = t.run()
        self.assertIsNone(result.included_files)


class EnvVarRedoResultTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_explicit_envvar_are_assigned_on_tool_instance(self):
        class BTool(dlb.ex.Tool):
            object_file = dlb.ex.Tool.Output.RegularFile()
            language = dlb.ex.Tool.Input.EnvVar(name='LANG',
                                                restriction=r'(?P<language>[a-z]{2})_(?P<territory>[A-Z]{2})',
                                                example='sv_SE')
            cflags = dlb.ex.Tool.Input.EnvVar(name='CFLAGS', restriction='.+', example='-O2', required=False)

            async def redo(self, result, context):
                pass

        t = BTool(object_file='a.o', language='de_CH')
        self.assertEqual({'language': 'de', 'territory': 'CH'}, t.language.groups)
        self.assertIsNone(t.cflags)

        t = BTool(object_file='a.o', language='de_CH', cflags='-Wall')
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

        class BTool(dlb.ex.Tool):
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

        t = BTool(object_file='a.o')
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


class ObjectRedoResultTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_nonexplicit_object_is_assigned_on_result(self):
        class BTool(dlb.ex.Tool):
            calculated = dlb.ex.Tool.Output.Object(explicit=False)

            async def redo(self, result, context):
                result.calculated = 42

        t = BTool()
        with dlb.ex.Context():
            r = t.run()
            self.assertTrue(r)
            self.assertEqual(42, r.calculated)


class RunToolDefinitionFileTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_redo_if_source_has_changed(self):

        with tempfile.TemporaryDirectory() as content_tmp_dir_path:
            open(os.path.join(content_tmp_dir_path, '__init__.py'), 'w').close()
            with open(os.path.join(content_tmp_dir_path, 'v.py'), 'w') as f:
                f.write(
                    'import dlb.ex\n'
                    'class A(dlb.ex.Tool):\n'
                    '    async def redo(self, result, context):\n'
                    '       pass'
                )

            zip_file_path = os.path.abspath('abc.zip')
            with zipfile.ZipFile(zip_file_path, 'w') as z:
                z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname='u3/__init__.py')
                z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname='u3/v.py')

        sys.path.insert(0, zip_file_path)
        # noinspection PyUnresolvedReferences
        import u3.v
        del sys.path[0]

        t = u3.v.A()

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_threshold_level(logging.DEBUG)
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            regex = r"\b()added 1 tool definition files as input dependency\n"
            self.assertRegex(output.getvalue(), regex)
            self.assertFalse(t.run())

        with zipfile.ZipFile(zip_file_path, 'w') as z:
            z.writestr('dummy', '')

        with dlb.ex.Context():
            output = io.StringIO()
            dlb.di.set_output_file(output)
            self.assertTrue(t.run())
            regex = r"\b()redo necessary because of filesystem object: 'abc.zip' \n"
            self.assertRegex(output.getvalue(), regex)


class ReprOfResultTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

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


class RunSummaryTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_no_runs_for_empty_successful(self):
        with dlb.ex.Context():
            pass

        with dlb.ex.Context():
            summaries = dlb.ex.Context.summary_of_latest_runs(max_count=10)

        self.assertEqual(1, len(summaries))
        summary = summaries[0]
        self.assertEqual(0, summary[2])
        self.assertEqual(0, summary[3])

    def test_no_summary_for_failed(self):
        with self.assertRaises(AssertionError):
            with dlb.ex.Context():
                assert False

        with dlb.ex.Context():
            summaries = dlb.ex.Context.summary_of_latest_runs(max_count=10)

        self.assertEqual(0, len(summaries))


class RunSummaryOutputTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_is_correct_without_previous_and_without_runs(self):
        dlb.cf.lastest_run_summary_max_count = 2
        output = io.StringIO()
        dlb.di.set_output_file(output)
        dlb.di.set_threshold_level(dlb.cf.level.INFO)

        with dlb.ex.Context():
            pass

        regex = (
            r"(?m)\A"
            r"I duration: [0-9.]+ s \n"
            r"  \| start +seconds +runs +redos \n"
            r"  \| [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+Z\* +[0-9.]+ +0 +0\n\Z"
        )
        self.assertRegex(output.getvalue(), regex)

    def test_is_correct_with_previous_and_with_runs(self):
        dlb.cf.lastest_run_summary_max_count = 2
        output = io.StringIO()
        dlb.di.set_output_file(output)
        dlb.di.set_threshold_level(dlb.cf.level.ERROR)

        t = ATool(source_file='a.cpp', object_file='a.o')
        open('a.cpp', 'xb').close()

        with dlb.ex.Context():
            self.assertTrue(t.run())
            self.assertTrue(t.run())
            self.assertFalse(t.run())

        with dlb.ex.Context():
            with dlb.ex.Context():
                self.assertFalse(t.run())
                self.assertTrue(t.run(force_redo=True))
            dlb.di.set_threshold_level(dlb.cf.level.INFO)

        regex = (
            r"(?m)\A"
            f"I duration compared to mean duration of previous 1 successful runs: [0-9.]+% of [0-9.]+ s \n"
            r"  \| start +seconds +runs +redos \n"
            r"  \| [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+Z +[0-9.]+ +3 +2 +\(66\.7%\) \n"
            r"  \| [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+Z\* +[0-9.]+ +2 +1 +\(50\.0%\)\n\Z"
        )
        self.assertRegex(output.getvalue(), regex)

    def test_ignores_invalid_configuration(self):
        dlb.cf.lastest_run_summary_max_count = []  # invalid
        output = io.StringIO()
        dlb.di.set_output_file(output)
        dlb.di.set_threshold_level(dlb.cf.level.INFO)

        with dlb.ex.Context():
            pass

        self.assertEqual("", output.getvalue())
