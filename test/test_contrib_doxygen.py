# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex
import dlb_contrib_doxygen
import unittest
import tools_for_test


class TemplateTest(unittest.TestCase):

    def test_braced_is_substituted(self):
        self.assertEqual('aXb', dlb_contrib_doxygen.Template('a${{A_as9_y}}b').substitute(A_as9_y='X'))

    def test_braced_with_invalid_name_is_not_substituted(self):
        self.assertEqual('a${{1a}}b', dlb_contrib_doxygen.Template('a${{1a}}b').substitute({'1a': 'X'}))

    def test_named_name_is_not_substituted(self):
        self.assertEqual('a$b', dlb_contrib_doxygen.Template('a$b').substitute({'b': 'X'}))

    def test_dollar_escaped(self):
        self.assertEqual('a${{x}}', dlb_contrib_doxygen.Template('a$${{x}}').substitute(x='X'))


class StringifyTest(unittest.TestCase):

    def test_single_is_correct(self):
        self.assertEqual('', dlb_contrib_doxygen._stringify_value(None))
        self.assertEqual('NO', dlb_contrib_doxygen._stringify_value(False))
        self.assertEqual('YES', dlb_contrib_doxygen._stringify_value(True))
        self.assertEqual('""', dlb_contrib_doxygen._stringify_value(''))
        self.assertEqual('27', dlb_contrib_doxygen._stringify_value(27))
        self.assertEqual('"1.25"', dlb_contrib_doxygen._stringify_value(1.25))
        self.assertEqual(dlb_contrib_doxygen._stringify_value(str(dlb.fs.Path('a').native)),
                         dlb_contrib_doxygen._stringify_value(dlb.fs.Path('a')))

    def test_fails_for_backslashquote(self):
        with self.assertRaises(ValueError):
            dlb_contrib_doxygen._stringify_value('\\"')

    def test_fails_for_nested_list(self):
        with self.assertRaises(ValueError):
            dlb_contrib_doxygen._stringify_value([1, 2, [3]])

    def test_iterable_is_correct(self):
        self.assertEqual('', dlb_contrib_doxygen._stringify_value([]))
        self.assertEqual('"a"', dlb_contrib_doxygen._stringify_value(['a']))
        self.assertEqual('\\\n    "a" \\\n    "b"', dlb_contrib_doxygen._stringify_value(['a', 'b']))


class DoxygenWithoutActualExecutionTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_backslashquote_in_path(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            dlb_contrib_doxygen.Doxygen(source_directories=['a\\"b'])
        msg = (
            "keyword argument for dependency role 'source_directories' is invalid: ['a\\\\\"b']\n"
            "  | reason: invalid path for 'Path': 'a\\\\\"b' (must not contain '\\\"')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_lf_in_path(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            dlb_contrib_doxygen.Doxygen(source_directories=['a\nb'])
        msg = (
            "keyword argument for dependency role 'source_directories' is invalid: ['a\\nb']\n"
            "  | reason: invalid path for 'Path': 'a\\nb' (must not contain these characters: '\\n','\\r')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_invalid_placeholder_name_type(self):
        class Doxygen(dlb_contrib_doxygen.Doxygen):
            TEXTUAL_REPLACEMENTS = {1: ''}

        open('Doxyfile', 'xb').close()

        with self.assertRaises(TypeError) as cm:
            with dlb.ex.Context():
                Doxygen(
                    configuration_template_file='Doxyfile',
                    source_directories=['.'],
                    output_directory='d/').run()
        self.assertEqual("placeholder name must be str", str(cm.exception))

    def test_fails_for_invalid_placeholder_name(self):
        class Doxygen(dlb_contrib_doxygen.Doxygen):
            TEXTUAL_REPLACEMENTS = {'1': ''}

        open('Doxyfile', 'xb').close()

        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                Doxygen(
                    configuration_template_file='Doxyfile',
                    source_directories=['.'],
                    output_directory='d/').run()
        self.assertEqual("invalid placeholder name: '1'", str(cm.exception))

    def test_fails_for_unexpanded_placeholder(self):
        class Doxygen(dlb_contrib_doxygen.Doxygen):
            TEXTUAL_REPLACEMENTS = {}

        with open('Doxyfile', 'wb') as f:
            f.write(b'${{xyz}}')

        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                Doxygen(
                    configuration_template_file='Doxyfile',
                    source_directories=['.'],
                    output_directory='d/').run()
        msg = (
            "unexpanded placeholder in configuration file template 'Doxyfile'\n"
            "  | file contains '${{xyz}}' but 'TEXTUAL_REPLACEMENTS' does not define a replacement"
        )
        self.assertEqual(msg, str(cm.exception))


@unittest.skipIf(not os.path.isfile('/usr/bin/doxygen'), 'requires doxygen')
class Doxygen2Test(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_empty_doxyfile(self):
        open('Doxyfile', 'xb').close()

        with dlb.ex.Context():
            dlb_contrib_doxygen.Doxygen(
                configuration_template_file='Doxyfile',
                source_directories=['.'],
                output_directory='d/').run()