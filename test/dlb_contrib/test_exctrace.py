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

        # noinspection PyTypeChecker
        sys.excepthook(Exception, Exception('[?]'), None)
        self.assertEqual(
            'C aborted by exception: \n'
            '  | Exception: [?] \n'
            '  | caused by:\n',
            output.getvalue())

        output = io.StringIO()
        dlb.di.set_output_file(output)
        try:
            raise Exception('[?]')
        except Exception as e:
            sys.excepthook(e.__class__, e, e.__traceback__)
        self.assertEqual(
            'C aborted by exception: \n'
            '  | Exception: [?] \n'
            '  | caused by: raise ...\n',
            output.getvalue())

        output = io.StringIO()
        dlb.di.set_output_file(output)
        try:
            try:
                raise Exception('[?]')
            except Exception:
                raise Exception('\ncaused by: this is not ambiguous')
        except Exception as e:
            sys.excepthook(e.__class__, e, e.__traceback__)
        self.assertEqual(
            'C aborted by exception: \n'
            '  | Exception: \n'
            '  | caused by: this is not ambiguous \n'
            '  | caused by: raise ...\n',
            output.getvalue())

        output = io.StringIO()
        dlb.di.set_output_file(output)
        try:
            assert False  # has to fail
        except Exception as e:
            sys.excepthook(e.__class__, e, e.__traceback__)
        self.assertEqual(
            'C aborted by exception: \n'
            '  | AssertionError \n'
            '  | caused by: assert False  # has to fail\n',
            output.getvalue())

        output = io.StringIO()
        dlb.di.set_output_file(output)
        try:
            exec('1 + ')
        except Exception as e:
            sys.excepthook(e.__class__, e, e.__traceback__)
        self.assertEqual(
            'C aborted by exception: \n'
            '  |   File "<string>", line 1 \n' 
            '  |     1 + \n'
            '  |        ^ \n' 
            '  | SyntaxError: invalid syntax \n'
            "  | caused by: exec('1 + ')\n",
            output.getvalue())

    def test_write_traceback_to_file(self):
        # noinspection PyBroadException
        try:
            raise Exception('[?]')
        except Exception:
            etype, value, tb = sys.exc_info()

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=0, traceback_file='traceback.log')
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)

        p = os.path.realpath('traceback.log')
        self.assertEqual(
            f"C aborted by exception: \n"
            f"  | Exception: [?] \n"
            f"  | caused by: \n"
            f"  | traceback: {p!r}\n",
            output.getvalue()
        )
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

        spec = importlib.util.spec_from_file_location('failing_script', os.path.realpath('failing_script.py'))
        module = importlib.util.module_from_spec(spec)

        # noinspection PyBroadException
        try:
            spec.loader.exec_module(module)
        except Exception:
            etype, value, tb = sys.exc_info()

        cwd = os.path.join(os.path.realpath(os.getcwd()), '')

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=3)
        output = io.StringIO()
        dlb.di.set_output_file(output)

        # noinspection PyUnboundLocalVariable
        sys.excepthook(etype, value, tb)
        msg = (
            f"C aborted by exception: \n"
            f"  | Exception: [?] \n"
            f"  | caused by: raise ...\n"
            f"  I involved lines from files in {cwd!r}: \n"
            f"    | 'failing_script.py':5 \n"
            f"    | 'failing_script.py':4 \n"
            f"    | 'failing_script.py':2 (nearest to cause)\n"
        )
        self.assertEqual(msg, output.getvalue())

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=2)
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)
        msg = (
            f"C aborted by exception: \n"
            f"  | Exception: [?] \n"
            f"  | caused by: raise ...\n"            
            f"  I involved lines from files in {cwd!r}: \n"
            f"    | 'failing_script.py':5 \n"
            f"    | 'failing_script.py':4 (nearest to cause) \n"
            f"    | ...\n"
        )
        self.assertEqual(msg, output.getvalue())

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=1)
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)
        msg = (
            f"C aborted by exception: \n"
            f"  | Exception: [?] \n"
            f"  | caused by: raise ...\n"            
            f"  I involved lines from files in {cwd!r}: \n"
            f"    | 'failing_script.py':5 (nearest to cause) \n"
            f"    | ...\n"
        )
        self.assertEqual(msg, output.getvalue())

        dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=0)
        output = io.StringIO()
        dlb.di.set_output_file(output)

        sys.excepthook(etype, value, tb)
        msg = (
            f"C aborted by exception: \n"
            f"  | Exception: [?] \n"
            f"  | caused by:\n"
        )
        self.assertEqual(msg, output.getvalue())

    def test_fails_for_nonint_limit(self):
        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            dlb_contrib.exctrace.enable_compact_with_cwd(involved_line_limit=1.5)
