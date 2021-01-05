# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.doxypress
import os.path
import shutil
import unittest


class TemplateTest(unittest.TestCase):

    def test_braced_is_substituted(self):
        self.assertEqual('aXb', dlb_contrib.doxypress.Template('a${{A_as9_y}}b').substitute(A_as9_y='X'))

    def test_braced_with_invalid_name_is_not_substituted(self):
        self.assertEqual('a${{1a}}b', dlb_contrib.doxypress.Template('a${{1a}}b').substitute({'1a': 'X'}))

    def test_named_name_is_not_substituted(self):
        self.assertEqual('a$b', dlb_contrib.doxypress.Template('a$b').substitute({'b': 'X'}))

    def test_dollar_escaped(self):
        self.assertEqual('a${{x}}', dlb_contrib.doxypress.Template('a$${{x}}').substitute(x='X'))


class DoxyPressWithoutActualExecutionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_invalid_placeholder_name_type(self):
        class DoxyPress(dlb_contrib.doxypress.DoxyPress):
            TEXTUAL_REPLACEMENTS = {1: ''}

        open('doxypress.json', 'xb').close()

        with self.assertRaises(TypeError) as cm:
            with dlb.ex.Context():
                DoxyPress(
                    project_template_file='doxypress.json',
                    source_directories=['.'],
                    output_directory='d/').start()
        self.assertEqual("placeholder name must be str", str(cm.exception))

    def test_fails_for_invalid_placeholder_name(self):
        class DoxyPress(dlb_contrib.doxypress.DoxyPress):
            TEXTUAL_REPLACEMENTS = {'1': ''}

        open('doxypress.json', 'xb').close()

        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                DoxyPress(
                    project_template_file='doxypress.json',
                    source_directories=['.'],
                    output_directory='d/').start()
        self.assertEqual("invalid placeholder name: '1'", str(cm.exception))

    def test_fails_for_unexpanded_placeholder(self):
        class DoxyPress(dlb_contrib.doxypress.DoxyPress):
            TEXTUAL_REPLACEMENTS = {}

        with open('doxypress.json', 'wb') as f:
            f.write(b'${{xyz}}')

        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                DoxyPress(
                    project_template_file='doxypress.json',
                    source_directories=['.'],
                    output_directory='d/').start()
        msg = (
            "unexpanded placeholder in project file template 'doxypress.json'\n"
            "  | file contains '${{xyz}}' but 'TEXTUAL_REPLACEMENTS' does not define a replacement"
        )
        self.assertEqual(msg, str(cm.exception))


@unittest.skipIf(not shutil.which('doxypress'), 'requires doxypress in $PATH')
class DoxyPressExecutionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_empty_doxyfile(self):
        open('doxypress.json', 'xb').close()

        with self.assertRaises(dlb.ex.HelperExecutionError):
            with dlb.ex.Context():
                dlb_contrib.doxypress.DoxyPress(
                    project_template_file='doxypress.json',
                    source_directories=['.'],
                    output_directory='d/').start()


@unittest.skipIf(not shutil.which('doxypress'), 'requires doxypress in $PATH')
class VersionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_version_is_string_with_dot(self):
        # noinspection PyPep8Naming
        Tool = dlb_contrib.doxypress.DoxyPress

        class QueryVersion(dlb_contrib.generic.VersionQuery):
            VERSION_PARAMETERS_BY_EXECUTABLE = {Tool.EXECUTABLE: Tool.VERSION_PARAMETERS}

        with dlb.ex.Context():
            version_by_path = QueryVersion().start().version_by_path
            path = dlb.ex.Context.active.helper[Tool.EXECUTABLE]
            self.assertEqual(1, len(version_by_path))
            version = version_by_path[path]
            self.assertIsInstance(version, str)
            self.assertGreaterEqual(version.count('.'), 2)
