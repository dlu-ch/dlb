# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import sys
import re
import logging
import time
import io
import collections
import unittest


class LoggingCompatibilityTest(unittest.TestCase):

    def test_levels_are_equals(self):
        for level_name in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            self.assertEqual(getattr(logging, level_name), getattr(dlb.di, level_name))


class GetLevelMarkerTest(unittest.TestCase):

    def test_exact_levels_are_correct(self):
        self.assertEqual('D', dlb.di.get_level_indicator(dlb.di.DEBUG))
        self.assertEqual('I', dlb.di.get_level_indicator(dlb.di.INFO))
        self.assertEqual('W', dlb.di.get_level_indicator(dlb.di.WARNING))
        self.assertEqual('E', dlb.di.get_level_indicator(dlb.di.ERROR))
        self.assertEqual('C', dlb.di.get_level_indicator(dlb.di.CRITICAL))

    def test_fails_for_positive_are_debug(self):
        msg = "'level' must be positive"

        with self.assertRaises(ValueError) as cm:
            dlb.di.get_level_indicator(logging.NOTSET)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.di.get_level_indicator(-123)
        self.assertEqual(msg, str(cm.exception))

    def test_exact_greater_than_critical_are_critical(self):
        self.assertEqual('C', dlb.di.get_level_indicator(dlb.di.CRITICAL + 123))

    def test_between_is_next_smaller(self):
        self.assertEqual('I', dlb.di.get_level_indicator(dlb.di.INFO + 1))
        self.assertEqual('I', dlb.di.get_level_indicator(dlb.di.WARNING - 1))


class FormatMessageTest(unittest.TestCase):
    
    def format_info_message(self, message):
        return dlb.di.format_message(message, dlb.di.INFO)

    def test_fails_on_empty(self):
        with self.assertRaises(ValueError) as cm:
            self.format_info_message('')
        msg = "'message' must contain at least one non-empty line"
        self.assertEqual(msg, str(cm.exception))

    def test_single_line_returns_stripped(self):
        self.assertEqual('I äüä schoo\U0001f609', self.format_info_message(' äüä schoo\U0001f609   '))

    def test_fails_for_none(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            self.format_info_message(None)
        msg = "'message' must be a str"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_bytes(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            self.format_info_message(b'abc')
        msg = "'message' must be a str"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_nonprintable(self):
        with self.assertRaises(ValueError) as cm:
            self.format_info_message('abc\n    a\0')
        msg = (
            "'message' must not contain ASCII control characters except "
            "'\\t' and '\\b', unlike '\\x00' in line 2"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_removed_empty_lines_before_and_after(self):
        m = self.format_info_message('   \n \n\n \na  \n    b\n\n   \n')
        self.assertEqual("I a \n  | b", m)

        m = self.format_info_message('   \r\n \r\n\r\n \r\na  \r\n    b\r\n\r\n   \r\n')
        self.assertEqual("I a \n  | b", m)

        m = self.format_info_message('   \r \r\r \ra  \r    b\r\r   \r')
        self.assertEqual("I a \n  | b", m)

    def test_removed_empty_lines_between(self):
        m = self.format_info_message('a\n\n\n    b\n    c')
        self.assertEqual("I a \n  | b \n  | c", m)

    def test_unindents(self):
        m = self.format_info_message(
            """
            bla
                a
                b
            """)
        self.assertEqual("I bla \n  | a \n  | b", m)

    def test_fails_for_underindented(self):
        with self.assertRaises(ValueError) as cm:
            self.format_info_message(
                """
                bla
                    x
                 y 
                """)
        msg = (
            "each continuation line in 'message' must be indented at least 4 spaces more than "
            "the first non-empty line, unlike line 4"
        )
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            self.format_info_message(
                """
                bla
                    x
               y 
                """)
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_reserved_start(self):
        with self.assertRaises(ValueError) as cm:
            self.format_info_message("'hehe'")
        msg = "first non-empty line in 'message' must not start with reserved character \"'\""
        self.assertEqual(msg, str(cm.exception))

    def test_field_are_justified(self):
        m = self.format_info_message(
            """
            a\tb33\t100\b
                a2\tb2\t10\b
                a33\tb\t1\b
            """)
        self.assertEqual('I a    b33100 \n  | a2 b2  10 \n  | a33b    1', m)

        m = self.format_info_message(
            """
            table:
                a:\t A =\b 1\b
                b2:\t B =\b 23\b
            """)
        self.assertEqual('I table: \n  | a:  A =  1 \n  | b2: B = 23', m)

    def test_fails_for_dot_at_end_of_first_line(self):
        with self.assertRaises(ValueError) as cm:
            self.format_info_message("start...")
        msg = "first non-empty line in 'message' must not end with '.'"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            self.format_info_message("done.")
        msg = "first non-empty line in 'message' must not end with '.'"
        self.assertEqual(msg, str(cm.exception))


class MessageThresholdTest(unittest.TestCase):

    def test_default_is_info(self):
        dlb.di.set_threshold_level(dlb.di.WARNING + 1)
        self.assertTrue(dlb.di.is_unsuppressed_level(dlb.di.WARNING + 1))
        self.assertFalse(dlb.di.is_unsuppressed_level(dlb.di.WARNING))

        dlb.di.set_threshold_level(dlb.di.CRITICAL + 100)
        self.assertTrue(dlb.di.is_unsuppressed_level(dlb.di.CRITICAL + 100))
        self.assertFalse(dlb.di.is_unsuppressed_level(dlb.di.CRITICAL + 99))

    def test_fails_on_nonpositve(self):
        with self.assertRaises(ValueError) as cm:
            dlb.di.set_threshold_level(0)
        msg = "'level' must be positive"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_on_none(self):
        with self.assertRaises(TypeError) as cm:
            dlb.di.set_threshold_level(None)
        msg = "'level' must be something convertible to an int"
        self.assertEqual(msg, str(cm.exception))


class SetOutputFileTest(unittest.TestCase):

    class File:
        def write(self, text: str):
            pass

    def test_fails_for_none(self):
        with self.assertRaises(TypeError) as cm:
            dlb.di.set_output_file(None)
        msg = "'file' does not have a 'write' method: None"
        self.assertEqual(msg, str(cm.exception))

    def test_successful_for_stdout_and_stderr(self):
        dlb.di.set_output_file(sys.stdout)
        r = dlb.di.set_output_file(sys.stderr)
        self.assertEqual(sys.stdout, r)
        r = dlb.di.set_output_file(sys.stderr)
        self.assertEqual(sys.stderr, r)

    def test_successful_for_custom_class_with_only_write(self):
        f = SetOutputFileTest.File()
        r = dlb.di.set_output_file(f)
        r = dlb.di.set_output_file(r)
        self.assertEqual(f, r)


class ClusterTest(unittest.TestCase):

    def setUp(self):
        dlb.di.set_threshold_level(dlb.di.INFO)
        _ = dlb.di._first_monotonic_ns  # make sure attribute exists
        dlb.di._first_monotonic_ns = None

    def test_works_as_context_manager(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        c = dlb.di.Cluster('A\n    a')
        self.assertEqual('', output.getvalue())  # does not output anything

        with c as cr:
            self.assertEqual('I A \n  | a\n', output.getvalue())  # does not output anything

        self.assertIsNone(cr)

    def test_cluster_do_nest(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.di.Cluster('A'):
            with dlb.di.Cluster('B'):
                with dlb.di.Cluster('C'):
                    pass
            with dlb.di.Cluster('D'):
                pass

        self.assertEqual('I A\n  I B\n    I C\n  I D\n', output.getvalue())  # does not output anything

    def test_level_threshold_is_observed_when_nested(self):
        dlb.di.set_threshold_level(dlb.di.WARNING)

        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.di.Cluster('A', level=dlb.di.ERROR):
            self.assertEqual('E A\n', output.getvalue())

            with dlb.di.Cluster('B'):
                self.assertEqual('E A\n', output.getvalue())

                with dlb.di.Cluster('C', level=dlb.di.WARNING):
                    self.assertEqual('E A\n  I B\n    W C\n', output.getvalue())

            with dlb.di.Cluster('D'):
                self.assertEqual('E A\n  I B\n    W C\n', output.getvalue())

    def test_progress_only_if_not_suppress_at_enter(self):
        dlb.di.set_threshold_level(dlb.di.WARNING)

        output = io.StringIO()
        dlb.di.set_output_file(output)
        with dlb.di.Cluster('A', is_progress=True):
            self.assertEqual('', output.getvalue())
        self.assertEqual('', output.getvalue())

        output = io.StringIO()
        dlb.di.set_output_file(output)
        with self.assertRaises(AssertionError):
            with dlb.di.Cluster('A', is_progress=True):
                assert False
        self.assertEqual('', output.getvalue())

    def test_progress_success_is_at_most_info(self):
        dlb.di.set_threshold_level(dlb.di.DEBUG)

        output = io.StringIO()
        dlb.di.set_output_file(output)
        with dlb.di.Cluster('A', level=dlb.di.DEBUG, is_progress=True):
            self.assertEqual('D A...\n', output.getvalue())
        self.assertEqual('D A...\n  D done.\n', output.getvalue())

        output = io.StringIO()
        dlb.di.set_output_file(output)
        with dlb.di.Cluster('A', level=dlb.di.CRITICAL, is_progress=True):
            self.assertEqual('C A...\n', output.getvalue())
        self.assertEqual('C A...\n  I done.\n', output.getvalue())  # at most dlb.di.INFO

    def test_progress_failure_is_at_least_error(self):
        dlb.di.set_threshold_level(dlb.di.DEBUG)

        output = io.StringIO()
        dlb.di.set_output_file(output)
        with self.assertRaises(AssertionError):
            with dlb.di.Cluster('A', level=dlb.di.DEBUG, is_progress=True):
                assert False
        self.assertEqual('D A...\n  E failed with AssertionError.\n', output.getvalue())  # at least dlb.di.ERROR

        output = io.StringIO()
        dlb.di.set_output_file(output)
        with self.assertRaises(AssertionError):
            with dlb.di.Cluster('A', level=dlb.di.CRITICAL, is_progress=True):
                assert False
        self.assertEqual('C A...\n  C failed with AssertionError.\n', output.getvalue())

    def test_timing_information_is_correct_for_delayed_output_of_title(self):
        dlb.di.set_threshold_level(dlb.di.WARNING)

        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.di.Cluster('A', with_time=True):
            self.assertEqual('', output.getvalue())
            time.sleep(0.1)

            with dlb.di.Cluster('B'):
                self.assertEqual('', output.getvalue())

                with dlb.di.Cluster('C', level=dlb.di.WARNING):
                    self.assertRegex(output.getvalue(), r'\A()I A \[\+0\.0+s\]\n  I B\n    W C\n\Z')

    def test_timing_information_is_correct_for_progress(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        regex = re.compile(r"(?m)(.|\n)* \[\+(?P<time>[0-9.]+)s\]\n\Z")

        with dlb.di.Cluster('A', with_time=True, is_progress=True):
            s = output.getvalue()
            m = regex.match(s)
            t0 = m.group('time')
            self.assertRegex(t0, r'\A()0\.0{1,9}\Z')
            time.sleep(0.1)

        s = output.getvalue()
        m = regex.match(s)
        t = m.group('time')
        self.assertNotEqual(t, t0, s)


class InformTest(unittest.TestCase):

    def setUp(self):
        dlb.di.set_threshold_level(dlb.di.INFO)
        _ = dlb.di._first_monotonic_ns  # make sure attribute exists
        dlb.di._first_monotonic_ns = None

    def test_output_without_cluster_is_not_indented(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)
        self.assertTrue(dlb.di.inform('M\n    m'))

        self.assertEqual('I M \n  | m\n', output.getvalue())

    def test_output_in_cluster_is_indented(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.di.Cluster('A'):
            self.assertTrue(dlb.di.inform('M\n    m'))
            self.assertEqual('I A\n  I M \n    | m\n', output.getvalue())

        dlb.di.set_threshold_level(dlb.di.WARNING)

        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.di.Cluster('A'):
            with dlb.di.Cluster('B'):
                self.assertTrue(dlb.di.inform('M\n    m', level=dlb.di.WARNING))
                self.assertEqual('I A\n  I B\n    W M \n      | m\n', output.getvalue())

    def test_suppresses_below_threshold(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)
        self.assertFalse(dlb.di.inform('M\n    m', level=dlb.di.DEBUG))
        self.assertEqual('', output.getvalue())

    def test_timing_information_is_correct(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)
        self.assertTrue(dlb.di.inform('M\n    m', with_time=True))
        self.assertRegex(output.getvalue(), r'\A()I M \[\+0\.0{1,9}s\] \n  \| m\n\Z')


class UsageExampleTest(unittest.TestCase):

    def setUp(self):
        dlb.di.set_threshold_level(dlb.di.INFO)
        _ = dlb.di._first_monotonic_ns  # make sure attribute exists
        dlb.di._first_monotonic_ns = None

    def test_example1(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        with dlb.di.Cluster('title', level=dlb.di.DEBUG):
            dlb.di.inform(
                """
                summary
                    first\t  1\t
                    second\t 200\t
                """)

        self.assertEqual('D title\n  I summary \n    | first   1 \n    | second 200\n', output.getvalue())

    def test_example2(self):
        output = io.StringIO()
        dlb.di.set_output_file(output)

        rom_max = 128
        logfile = dlb.fs.Path('out/linker.log')

        with dlb.di.Cluster(f"analyze memory usage\n    see {logfile.as_string()!r} for details",
                            is_progress=True):
            ram, rom, emmc = (12, 108, 512)

            dlb.di.inform(
                f"""
                in use:
                    RAM:\t {ram}\b kB
                    ROM (NOR flash):\t {rom}\b kB
                    eMMC:\t {emmc}\b kB
                """)

            if rom > 0.8 * rom_max:
                dlb.di.inform("more than 80% of ROM used", level=dlb.di.WARNING)

        o = (
            "I analyze memory usage... \n"
            "  | see 'out/linker.log' for details\n"
            "  I in use: \n"
            "    | RAM:              12 kB \n"
            "    | ROM (NOR flash): 108 kB \n"
            "    | eMMC:            512 kB\n"
            "  W more than 80% of ROM used\n"
            "  I done.\n"
        )
        self.assertEqual(o, output.getvalue())

    def test_example3(self):
        # https://en.wikipedia.org/wiki/Halstead_complexity_measures
        metrics = [
            ('volume', 'V', 1.7, ''),
            ('programming required', 'T', 127.3, ' s'),
            ('difficulty', 'D', 12.8, '')
        ]

        m = ''.join(f"\n    {n}:\t {s} =\b {v}\b{u}" for n, s, v, u in metrics)
        s = dlb.di.format_message('Halstead complexity measures:' + m, dlb.di.INFO)

        o = (
            "I Halstead complexity measures: \n" 
            "  | volume:               V =   1.7 \n" 
            "  | programming required: T = 127.3 s \n"
            "  | difficulty:           D =  12.8"
        )
        self.assertEqual(o, s)
