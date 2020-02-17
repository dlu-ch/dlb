# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.di
import dlb.fs
import logging
import collections
import unittest


class GetLevelMarkerTest(unittest.TestCase):

    def test_exact_levels_are_correct(self):
        self.assertEqual('D', dlb.di.get_level_marker(logging.DEBUG))
        self.assertEqual('I', dlb.di.get_level_marker(logging.INFO))
        self.assertEqual('W', dlb.di.get_level_marker(logging.WARNING))
        self.assertEqual('E', dlb.di.get_level_marker(logging.ERROR))
        self.assertEqual('C', dlb.di.get_level_marker(logging.CRITICAL))

    def test_fails_for_positive_are_debug(self):
        msg = "'level' must be > 0"

        with self.assertRaises(ValueError) as cm:
            dlb.di.get_level_marker(logging.NOTSET)
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.di.get_level_marker(-123)
        self.assertEqual(msg, str(cm.exception))

    def test_exact_greater_than_critical_are_critical(self):
        self.assertEqual('C', dlb.di.get_level_marker(logging.CRITICAL + 123))

    def test_between_is_next_smaller(self):
        self.assertEqual('I', dlb.di.get_level_marker(logging.INFO + 1))
        self.assertEqual('I', dlb.di.get_level_marker(logging.WARNING - 1))


class FormatMultilineMessageTest(unittest.TestCase):
    
    def format_info_message(self, message):
        return dlb.di.format_message(message, logging.INFO)

    def test_fails_on_empty(self):
        with self.assertRaises(ValueError) as cm:
            self.format_info_message('')
        msg = "'message' must contain at least one non-empty line"
        self.assertEqual(msg, str(cm.exception))

    def test_single_line_returns_stripped(self):
        self.assertEqual('I bla', self.format_info_message(' bla   '))

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
            "'message' must only contain printable ASCII characters except "
            "'\\t' and '\\b', unlike '\\x00' in line 2"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_removed_empty_lines_before_and_after(self):
        m = self.format_info_message('   \n \r\n \ra\n    b\n\n   \n')
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
        msg = (
            "each continuation line in 'message' must be indented at least 4 spaces more than "
            "the first non-empty line, unlike line 4"
        )

        with self.assertRaises(ValueError) as cm:
            self.format_info_message(
                """
                bla

               x 
                """)
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

    def test_fails_for_dot_at_end_of_first_line(self):
        with self.assertRaises(ValueError) as cm:
            self.format_info_message("start...")
        msg = "first non-empty line in 'message' must not end with '.'"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            self.format_info_message("done.")
        msg = "first non-empty line in 'message' must not end with '.'"
        self.assertEqual(msg, str(cm.exception))


class UsageExampleTest(unittest.TestCase):

    def test_example1(self):
        with dlb.di.Cluster('title', level=logging.DEBUG):
            dlb.di.inform(
                """
                summary
                    first\t  1\t
                    second\t 200\t
                """)

    def test_example2(self):
        rom_max = 128
        logfile = dlb.fs.Path('out/linker.log')

        with dlb.di.Cluster(f"analyze memory usage\n    note: see {logfile.as_string()!r} for details", is_progress=True):
            ram, rom, emmc = (12, 108, 512)

            dlb.di.inform(
                f"""
                in use:
                    RAM:\t {ram}\b kB
                    ROM (NOR flash):\t {rom}\b kB
                    eMMC:\t {emmc}\b kB
                """)

            if rom > 0.8 * rom_max:
                dlb.di.inform("more than 80 % of ROM used", level=logging.WARNING)
