# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb_contrib_lang_make as make
import unittest


class ParseRuleTest(unittest.TestCase):

    def test_typical_single_line(self):
        r = make.sources_from_rules(['a.o: a.c /usr/include/x86_64-linux-gnu/bits/types.h a.h b.h'])
        self.assertEqual([['a.c', '/usr/include/x86_64-linux-gnu/bits/types.h', 'a.h', 'b.h']], r)

        r = make.sources_from_rules(['a.o : a.c /usr/include/x86_64-linux-gnu/bits/types.h a.h b.h ;'])
        self.assertEqual([['a.c', '/usr/include/x86_64-linux-gnu/bits/types.h', 'a.h', 'b.h']], r)

    def test_without_sources(self):
        r = make.sources_from_rules(['a.o:'])
        self.assertEqual([[]], r)

    def test_multiple_target(self):
        r = make.sources_from_rules(['a.o b.o: x.h'])
        self.assertEqual([['x.h']], r)

    def test_unquoted_backslash(self):
        r = make.sources_from_rules(['a.o: a.c a\\b.h'])
        self.assertEqual([['a.c', 'a\\b.h']], r)

    def test_percent(self):
        r = make.sources_from_rules(['a.o: %.c'])
        self.assertEqual([['%.c']], r)

        r = make.sources_from_rules(['a.o: \\%.c'])
        self.assertEqual([['\\%.c']], r)

    def test_whitespace_other_than_space(self):
        r = make.sources_from_rules(['a.o: \t\v a.c\ta\\b.h'])
        self.assertEqual([['a.c', 'a\\b.h']], r)

    def test_quoted_special(self):
        r = make.sources_from_rules(['a.o: \\#$$\\:\\;\\*\\?\\[\\]\\ \\\t.c'])
        self.assertEqual([['#$:;*?[] \t.c']], r)

        r = make.sources_from_rules(['a.o: \\\\.c'])  # '\\' cannot be quoted with '\\
        self.assertEqual([['\\\\.c']], r)

    def test_combines_continuation_line(self):
        # note: '\\' must be last character on line; it is an error to place a comment after '\\' on the same line
        r = make.sources_from_rules(['a.o: a.c a\\', '.h'])
        self.assertEqual([['a.c', 'a', '.h']], r)

        r = make.sources_from_rules(['a.o: a.c \\', 'b.h b.c'])
        self.assertEqual([['a.c', 'b.h', 'b.c']], r)

        r = make.sources_from_rules(['a.o: a.c \\', '\techo'])
        self.assertEqual([['a.c', 'echo']], r)

        r = make.sources_from_rules(['a.o: a.c # \\', 'b.o: b.c'])  # even in comment
        self.assertEqual([['a.c']], r)

    def test_fails_for_multiple_backslashes_at_end_of_line(self):
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: a.c\\\\'])

    def test_fails_or_filename_with_in_colon(self):
        # this includes absolute Windows path like (the special handling of GNU Make with HAVE_DOS_PATHS is ignored)
        # note: gcc 8.3.0 erroneously outputs such rules with -MM
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: a.c a:b'])

    def test_fails_for_missing_colon(self):
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o a.c'])

    def test_fails_for_multiple_colons(self):
        with self.assertRaises(ValueError):
            make.sources_from_rules(['x: a.o: a.c'])
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o:: a.c'])

    def test_fails_for_unquoted_dollar(self):
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: a$'])
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: $a'])
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: \\$a'])  # '$' cannot be quoted with '\\'
        with self.assertRaises(ValueError):
            # example from https://www.gnu.org/software/make/manual/html_node/Splitting-Lines.html
            make.sources_from_rules(['a.o: one$\\', 'word'])

    def test_fails_for_unquoted_wildcard(self):
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: a*'])
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: a?'])
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: a['])
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: a]'])

    def test_fails_for_unquoted_percent_in_target(self):
        with self.assertRaises(ValueError):
            make.sources_from_rules(['%.o: %.c'])

    def test_fails_for_continuation_at_end(self):
        with self.assertRaises(ValueError):
            make.sources_from_rules(['a.o: a.c a\\'])  # ends with continuation line

    def test_ignores_comment(self):
        r = make.sources_from_rules(['a.o: a.c # a.h', 'b.o: b.c'])
        self.assertEqual([['a.c'], ['b.c']], r)

        r = make.sources_from_rules(['a.o: a.c # a.h\\', 'b.o: b.c', 'c.o: c.c'])
        self.assertEqual([['a.c'], ['c.c']], r)

    def test_ignores_command(self):
        r = make.sources_from_rules(['a.o: a.c', '\tb.o: b.c'])
        self.assertEqual([['a.c']], r)

        r = make.sources_from_rules(['a.o: a.c ; echo', '\tb.o: b.c'])
        self.assertEqual([['a.c']], r)

        r = make.sources_from_rules(['a.o: a.c; echo', '\tb.o: b.c'])
        self.assertEqual([['a.c']], r)

        r = make.sources_from_rules(['a.o: a.c a\\b.h', '\techo a', '\t$(CC) -c -o $@ $< $(CFLAGS)'])
        self.assertEqual([['a.c', 'a\\b.h']], r)

    def test_empty_(self):
        r = make.sources_from_rules(['a.o: ;'])
        self.assertEqual([[]], r)

    def test_ignores_empty_and_commentonly_lines(self):
        r = make.sources_from_rules(['', '       ',  '#  a.o: a.c', '  ', 'a.o: a.c', '', '#'])
        self.assertEqual([['a.c']], r)
