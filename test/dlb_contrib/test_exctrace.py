# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb_contrib.exctrace
import sys
import os.path
import io
import traceback
import importlib.util
import unittest
import dlb.di

class ThisIsAUnitTest(unittest.TestCase):
    pass


class EnableCompactWithCwdTest(testenv.TemporaryWorkingDirectoryTestCase):
    def test_sets_excepthook(self):
        previous = sys.excepthook
        dlb_contrib.exctrace.enable_compact_with_cwd()
        self.assertIsNot(sys.excepthook, previous)
        sys.excepthook = previous

    def test_outputs_to_dlb_di(self):
        dlb_contrib.exctrace.enable_compact_with_cwd()
        output = io.StringIO()
        dlb.di.set_output_file(output)
        sys.excepthook(Exception, Exception('[?]'), None)
        self.assertEqual("C aborted by exception: \n  | 'Exception: [?]'\n", output.getvalue())

    def test_write_traceback_to_file(self):
        try:
            raise Exception('[?]')
        except Exception:
            etype, value, tb = sys.exc_info()

        dlb_contrib.exctrace.enable_compact_with_cwd(traceback_file='traceback.log')
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)

        p = os.path.realpath('traceback.log')
        self.assertEqual(f"C aborted by exception: \n  | 'Exception: [?]' \n  | traceback: {p!r}\n", output.getvalue())
        with open('traceback.log', 'r') as f:
            content = f.read()
        self.assertTrue(content.startswith('Traceback (most recent call last):'))
        self.assertIn('\nException: [?]\n', content)

    def test_write_traceback_to_file(self):
        try:
            raise Exception('[?]')
        except Exception:
            etype, value, tb = sys.exc_info()

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=0, traceback_file='traceback.log')
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)

        p = os.path.realpath('traceback.log')
        self.assertEqual(f"C aborted by exception: \n  | 'Exception: [?]' \n  | traceback: {p!r}\n", output.getvalue())
        with open('traceback.log', 'r') as f:
            content = f.read()
        self.assertTrue(content.startswith('Traceback (most recent call last):'))
        self.assertIn('\nException: [?]\n', content)

    def test_includes_involved_in_cwd(self):
        with open('failing_script.py', 'x') as f:
            f.write(
                'def g(x):\n'
                '    raise Exception("[?]")\n'
                'def f():\n'
                '  g(False)\n'
                'f()\n'
            )
            f.write('assert False\n')

        spec = importlib.util.spec_from_file_location('failing_script', os.path.realpath('failing_script.py'))
        module = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except Exception:
            etype, value, tb = sys.exc_info()

        cwd = os.path.join(os.path.realpath(os.getcwd()), '')

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=3)
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)
        msg = (
            "C aborted by exception: \n"
            "  | 'Exception: [?]'\n"
            f"  I involved lines from files in {cwd!r}: \n"
            "    | 'failing_script.py':5 \n"
            "    | 'failing_script.py':4 \n"
            "    | 'failing_script.py':2 (nearest to cause)\n"
        )
        self.assertEqual(msg, output.getvalue())

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=2)
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)
        msg = (
            "C aborted by exception: \n"
            "  | 'Exception: [?]'\n"
            f"  I involved lines from files in {cwd!r}: \n"
            "    | 'failing_script.py':5 \n"
            "    | 'failing_script.py':4 (nearest to cause) \n"
            "    | ...\n"
        )
        self.assertEqual(msg, output.getvalue())

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=1)
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)
        msg = (
            "C aborted by exception: \n"
            "  | 'Exception: [?]'\n"
            f"  I involved lines from files in {cwd!r}: \n"
            "    | 'failing_script.py':5 (nearest to cause) \n"
            "    | ...\n"
        )
        self.assertEqual(msg, output.getvalue())

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=0)
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)
        msg = (
            "C aborted by exception: \n"
            "  | 'Exception: [?]'\n"
        )
        self.assertEqual(msg, output.getvalue())

    def test_fails_for_nonint_limit(self):
        with self.assertRaises(TypeError):
            dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=1.5)
