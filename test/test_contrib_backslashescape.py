# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))


import dlb_contrib.backslashescape
import unittest


class UnquoteBytesTest(unittest.TestCase):

    def test_replaces_escape_sequences(self):
        self.assertEqual(b'', dlb_contrib.backslashescape.unquote(b'', opening=None))
        self.assertEqual(b'\\', dlb_contrib.backslashescape.unquote(b'\\\\', opening=None))
        self.assertEqual(b'\\\\', dlb_contrib.backslashescape.unquote(b'\\\\\\\\', opening=None))
        self.assertEqual(b'\\\n', dlb_contrib.backslashescape.unquote(b'\\\\\\n', opening=None))
        self.assertEqual(b'a"b\'c', dlb_contrib.backslashescape.unquote(b'a\\"b\\\'c', opening=None))
        self.assertEqual(b'a\ab\fc\nd\re\tf\vg',
                         dlb_contrib.backslashescape.unquote(b'a\\ab\\fc\\nd\\re\\tf\\vg', opening=None))
        self.assertEqual(b'a\x1F2b\1234\0z\x01',
                         dlb_contrib.backslashescape.unquote(b'a\\x1F2b\\1234\\0z\\x1', opening=None))

    def test_fails_for_incomplete_escape_sequence(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'a\\', opening=None)
        self.assertEqual("truncated escape sequence", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'a\\_', opening=None)
        self.assertEqual("unknown escape sequence: '\\\\_'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'a\\x', opening=None)
        self.assertEqual("truncated \\xXX escape sequence", str(cm.exception))

    def test_fails_for_disabled_hexadecimal_sequence(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'\\xAB', with_hex=False, opening=None)
        self.assertEqual("unknown escape sequence: '\\\\x'", str(cm.exception))

    def test_fails_for_disabled_octal_sequence(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'\\123', with_oct=False, opening=None)
        self.assertEqual("unknown escape sequence: '\\\\1'", str(cm.exception))

    def test_removes_delimiters(self):
        self.assertEqual(b'abc', dlb_contrib.backslashescape.unquote(b'<abc>', {}, opening='<', closing='>'))

    def test_fails_for_invalid_delimiter(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb_contrib.backslashescape.unquote(b'', with_oct=False, opening=b'')
        self.assertEqual("'opening' must be None or a string", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'', with_oct=False, opening='')
        self.assertEqual("'opening' must contain exactly one character", str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb_contrib.backslashescape.unquote(b'', with_oct=False, closing=b'')
        self.assertEqual("'closing' must be None or a string", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'', with_oct=False, closing='')
        self.assertEqual("'closing' must contain exactly one character", str(cm.exception))

    def test_fails_for_invalid_delimiter2(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'', with_oct=False, opening='"')
        self.assertEqual("'literal' not delimited by '\"' and '\"': b''", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'"a', with_oct=False, opening='"')
        self.assertEqual("'literal' not delimited by '\"' and '\"': b'\"a'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'<a<', with_oct=False, opening='<', closing='>')
        self.assertEqual("'literal' not delimited by '<' and '>': b'<a<'", str(cm.exception))

    def test_fails_for_unescaped_delimiter_between(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote(b'<a<>', with_oct=False, opening='<', closing='>')
        self.assertEqual("'literal' must not contain an unescaped '<': b'<a<>'", str(cm.exception))
        self.assertEqual(b'a<', dlb_contrib.backslashescape.unquote(b'<a\\<>', {'<': ord('<')},
                                                                   opening='<', closing='>'))


class UnquoteStrTest(unittest.TestCase):

    def test_replaces_escape_sequences(self):
        self.assertEqual('', dlb_contrib.backslashescape.unquote('', opening=None))
        self.assertEqual('\\', dlb_contrib.backslashescape.unquote('\\\\', opening=None))
        self.assertEqual('\\\\', dlb_contrib.backslashescape.unquote('\\\\\\\\', opening=None))
        self.assertEqual('\\\n', dlb_contrib.backslashescape.unquote('\\\\\\n', opening=None))
        self.assertEqual('a"b\'c', dlb_contrib.backslashescape.unquote('a\\"b\\\'c', opening=None))
        self.assertEqual('a\ab\fc\nd\re\tf\vg',
                         dlb_contrib.backslashescape.unquote('a\\ab\\fc\\nd\\re\\tf\\vg', opening=None))
        self.assertEqual('a\x1F2b\1234\0z\x01',
                         dlb_contrib.backslashescape.unquote('a\\x1F2b\\1234\\0z\\x1', opening=None))

    def test_fails_for_incomplete_escape_sequence(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote('a\\', opening=None)
        self.assertEqual("truncated escape sequence", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote('a\\_', opening=None)
        self.assertEqual("unknown escape sequence: '\\\\_'", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote('a\\x', opening=None)
        self.assertEqual("truncated \\xXX escape sequence", str(cm.exception))

    def test_fails_for_disabled_hexadecimal_sequence(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote('\\xAB', {}, with_hex=False, opening=None)
        self.assertEqual("unknown escape sequence: '\\\\x'", str(cm.exception))

    def test_fails_for_disabled_octal_sequence(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.backslashescape.unquote('\\123', {}, with_oct=False, opening=None)
        self.assertEqual("unknown escape sequence: '\\\\1'", str(cm.exception))
