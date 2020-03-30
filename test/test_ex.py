# SPDX-License-Identifier: LGPL-3.0-or-later
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
import io
import unittest
import tools_for_test


class ImportTest(unittest.TestCase):

    def test_all_from_tool_is_correct(self):
        import dlb.ex.tool
        self.assertEqual({
            'Tool',
            'DefinitionAmbiguityError',
            'DependencyError',
            'DependencyError',
            'ExecutionParameterError',
            'RedoError',
            'HelperExecutionError',
            'is_complete'},
            set(dlb.ex.tool.__all__))
        self.assertTrue('Tool' in dir(dlb.ex))

        for n in dlb.ex.tool.__all__:
            self.assertEqual('dlb.ex', dlb.ex.tool.__dict__[n].__module__)

    def test_all_from_context_is_correct(self):
        import dlb.ex.context
        self.assertEqual({
            'Context',
            'ReadOnlyContext',
            'ContextNestingError',
            'NotRunningError',
            'ManagementTreeError',
            'NoWorkingTreeError',
            'WorkingTreeTimeError',
            'ContextModificationError',
            'WorkingTreePathError'},
            set(dlb.ex.context.__all__))
        self.assertTrue('Context' in dir(dlb.ex))

        for n in dlb.ex.context.__all__:
            self.assertEqual('dlb.ex', dlb.ex.context.__dict__[n].__module__)


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
        orig = dlb.cf.latest_run_summary_max_count
        try:
            dlb.cf.latest_run_summary_max_count = 2
            output = io.StringIO()
            dlb.di.set_output_file(output)
            dlb.di.set_threshold_level(dlb.di.INFO)

            with dlb.ex.Context():
                pass

            regex = (
                r"(?m)\A"
                r"I duration: [0-9.]+ s \n"
                r"  \| start +seconds +runs +redos \n"
                r"  \| [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+Z\* +[0-9.]+ +0 +0\n\Z"
            )
            self.assertRegex(output.getvalue(), regex)
        finally:
            dlb.cf.latest_run_summary_max_count = orig

    def test_is_correct_with_previous_and_with_runs(self):
        orig = dlb.cf.latest_run_summary_max_count

        try:
            dlb.cf.latest_run_summary_max_count = 2
            output = io.StringIO()
            dlb.di.set_output_file(output)
            dlb.di.set_threshold_level(dlb.di.ERROR)

            class ATool(dlb.ex.Tool):
                source_file = dlb.ex.Tool.Input.RegularFile()
                object_file = dlb.ex.Tool.Output.RegularFile()
                included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

                async def redo(self, result, context):
                    dlb.di.inform("redoing right now")

                    with (context.root_path / self.object_file).native.raw.open('wb'):
                        pass

                    result.included_files = [dlb.fs.Path('a.h'), dlb.fs.Path('b.h')]

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
                dlb.di.set_threshold_level(dlb.di.INFO)

            regex = (
                r"(?m)\A"
                f"I duration compared to mean duration of previous 1 successful runs: [0-9.]+% of [0-9.]+ s \n"
                r"  \| start +seconds +runs +redos \n"
                r"  \| [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+Z +[0-9.]+ +3 +2 +\(66\.7%\) \n"
                r"  \| [0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+Z\* +[0-9.]+ +2 +1 +\(50\.0%\)\n\Z"
            )
            self.assertRegex(output.getvalue(), regex)

        finally:
            dlb.cf.latest_run_summary_max_count = orig

    def test_ignores_invalid_configuration(self):
        orig = dlb.cf.latest_run_summary_max_count
        try:
            dlb.cf.latest_run_summary_max_count = []  # invalid
            output = io.StringIO()
            dlb.di.set_output_file(output)
            dlb.di.set_threshold_level(dlb.di.INFO)

            with dlb.ex.Context():
                pass

            self.assertEqual("", output.getvalue())
        finally:
            dlb.cf.latest_run_summary_max_count = orig

