# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path

here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb_contrib_c
import textwrap
import unittest
import tools_for_test


class RegexTest(unittest.TestCase):

    def test_identifier(self):
        self.assertTrue(dlb_contrib_c.IDENTIFIER.match('_a1Z'))
        self.assertTrue(dlb_contrib_c.IDENTIFIER.match('a' * 63))

        self.assertFalse(dlb_contrib_c.IDENTIFIER.match(''))
        self.assertFalse(dlb_contrib_c.IDENTIFIER.match('1a'))
        self.assertFalse(dlb_contrib_c.IDENTIFIER.match('a' * 64))

    def test_macro(self):
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z()'))
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(x)'))
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(...)'))
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(x, y, ...)'))
        self.assertTrue(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(  x  , y  , ...  )'))

        self.assertEqual('_a1Z', dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(x, y, ...)').group('name'))
        self.assertEqual('x, y, ...', dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z(x, y, ...)').group('arguments'))

        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z'))
        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z ()'))
        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z('))
        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z( ..., x )'))
        self.assertFalse(dlb_contrib_c.FUNCTIONLIKE_MACRO.match('_a1Z( x, ..., y )'))


class StringLiteralFromBytesTest(unittest.TestCase):

    def test_typical_is_unchanged(self):
        self.assertEqual('""', dlb_contrib_c.string_literal_from_bytes(b''))
        self.assertEqual('"abc 42!"', dlb_contrib_c.string_literal_from_bytes(b'abc 42!'))

    def test_non_printable_and_quote_is_replaced(self):
        self.assertEqual('"a\\x0A\\x22\\x60\\x5Cx"', dlb_contrib_c.string_literal_from_bytes(b'a\n"`\\x'))

    def test_contains_no_hexdigit_after_escape(self):
        self.assertEqual('"a\\x0A" "b\\x00" "F\\x22" "b"', dlb_contrib_c.string_literal_from_bytes(b'a\nb\0F"b'))

    def test_contains_no_trigraph(self):
        s = dlb_contrib_c.string_literal_from_bytes(b'a??=b')
        self.assertNotIn('??', s)

    def test_break_long_into_several_lines(self):
        s = dlb_contrib_c.string_literal_from_bytes(b'.' * 10, 5)
        self.assertEqual('"..."\n"..."\n"..."\n"."', s)
        s = dlb_contrib_c.string_literal_from_bytes(b'.' * 3, 0)
        self.assertEqual('"."\n"."\n"."', s)

        s = dlb_contrib_c.string_literal_from_bytes(b'abc\n', 9)
        self.assertEqual('"abc\\x0A"', s)
        s = dlb_contrib_c.string_literal_from_bytes(b'abc\n', 8)
        self.assertEqual('"abc"\n"\\x0A"', s)

        s = dlb_contrib_c.string_literal_from_bytes(b'abc\nd', 13)
        self.assertEqual('"abc\\x0A" "d"', s)
        s = dlb_contrib_c.string_literal_from_bytes(b'abc\nd', 12)
        self.assertEqual('"abc\\x0A"\n"d"', s)
        s = dlb_contrib_c.string_literal_from_bytes(b'abc\nd', 9)
        self.assertEqual('"abc\\x0A"\n"d"', s)


class IdentifierLikeFromStringTest(unittest.TestCase):

    def test_only_basecharacters(self):
        s = dlb_contrib_c.identifier_like_from_string('')
        self.assertEqual('_', s)

        s = dlb_contrib_c.identifier_like_from_string('abC_Def_')
        self.assertEqual('abC_Def__', s)

    def test_mixed(self):
        s = dlb_contrib_c.identifier_like_from_string('Säu\\li')
        self.assertEqual('S_u_li_08V02I', s)

        s = dlb_contrib_c.identifier_like_from_string('test.h')
        self.assertEqual('test_h_06D', s)

    def test_special_slash(self):
        s = dlb_contrib_c.identifier_like_from_string('src/generated/version.h', sep='/')
        self.assertEqual('src_generated_version_h_26D', s)


class IdentifierFromPathTest(unittest.TestCase):

    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError):
            dlb_contrib_c.identifier_from_path(dlb.fs.Path('/a'))

    def test_dot(self):
        s = dlb_contrib_c.identifier_from_path(dlb.fs.Path('.'))
        self.assertEqual('_', s)

    def test_dotdot(self):
        s = dlb_contrib_c.identifier_from_path(dlb.fs.Path('../'))
        self.assertEqual('____06D06D', s)

    def test_typical_source_file_path(self):
        s = dlb_contrib_c.identifier_from_path(dlb.fs.Path('src'))
        self.assertEqual('SRC_', s)

        s = dlb_contrib_c.identifier_from_path(dlb.fs.Path('src/io/print.h'))
        self.assertEqual('SRC_IO_PRINT_H_26D', s)

    def test_typical_file_path(self):
        s = dlb_contrib_c.identifier_from_path(dlb.fs.Path('s-rc/i_o/p+rint.h'))
        self.assertEqual('S_RC_I_O_P_RINT_H_05D15I13D06D', s)

    def test_untypical_file_path(self):
        s = dlb_contrib_c.identifier_from_path(dlb.fs.Path('säü\\li'))
        self.assertEqual('S___LI_06S00V02I', s)


class GenerateHeaderFileTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_scenario1(self):

        class GenerateVersionFile(dlb_contrib_c.GenerateHeaderFile):
            COMPONENT_ID = 42
            VERSION = '1.2.3c4-dev2+a2d66f1d?'

            PATH_COMPONENTS_TO_STRIP = 1

            def write_content(self, open_file):
                version = dlb_contrib_c.string_literal_from_bytes(self.VERSION.encode())
                open_file.write(f'#define COMPONENT_{self.COMPONENT_ID}_WD_VERSION {version}\n')

        os.makedirs(os.path.join('src', 'Generated'))

        with dlb.ex.Context():
            GenerateVersionFile(file='src/Generated/Version.h').run()

        with open(os.path.join('src', 'Generated', 'Version.h'), 'r') as f:
            content = f.read()

        expected_content = \
            """
            // This file was created automatically.
            // Do not modify it manually.
            
            #ifndef GENERATED_VERSION_H_16D_
            #define GENERATED_VERSION_H_16D_
            
            #define COMPONENT_42_WD_VERSION "1.2.3c4-dev2+a2d66f1d?"
            
            #endif  // GENERATED_VERSION_H_16D_
            """
        self.assertEqual(textwrap.dedent(expected_content).lstrip(), content)

    def test_creates_include_guard(self):

        with dlb.ex.Context():
            dlb_contrib_c.GenerateHeaderFile(file='Version.h').run()

        with open('Version.h', 'r') as f:
            content = f.read()

        expected_content = \
            """
            // This file was created automatically.
            // Do not modify it manually.

            #ifndef VERSION_H_06D_
            #define VERSION_H_06D_


            #endif  // VERSION_H_06D_
            """
        self.assertEqual(textwrap.dedent(expected_content).lstrip(), content)

    def test_fails_for_nonidentifier_guard(self):

        class GenerateVersionFile(dlb_contrib_c.GenerateHeaderFile):
            INCLUDE_GUARD_PREFIX = '1'

            def write_content(self, open_file):
                pass

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                GenerateVersionFile(file='empty.h').run()

    def test_fails_for_too_many_stripped_components(self):

        class GenerateVersionFile(dlb_contrib_c.GenerateHeaderFile):
            PATH_COMPONENTS_TO_STRIP = 1

            def write_content(self, open_file):
                pass

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                GenerateVersionFile(file='empty.h').run()