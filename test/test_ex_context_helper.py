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
import unittest
import tools_for_test


class BinarySearchPathNotRunningTest(unittest.TestCase):

    def test_fails_if_not_running(self):
        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex.NotRunningError):
            c.binary_search_paths


class BinarySearchPathTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_is_nonempty_tuple_of_absolute_paths(self):
        with dlb.ex.Context():
            paths = dlb.ex.Context.binary_search_paths

        self.assertIsInstance(paths, tuple)
        self.assertGreater(len(paths), 0)
        for p in paths:
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(p.is_absolute())

        self.assertEqual(len(set(paths)), len(paths))


class FindPathInNotRunningTest(unittest.TestCase):

    def test_fails_if_not_running(self):
        with self.assertRaises(dlb.ex.NotRunningError):
            dlb.ex.Context.find_path_in('a', [])


class FindPathInTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_absolute(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.find_path_in('/a', [])
        self.assertEqual("'path' must not be absolute", str(cm.exception))

    def test_fails_for_str_or_bytes(self):
        msg = "'search_prefixes' must be iterable (other than 'str' or 'bytes')"

        with dlb.ex.Context():
            with self.assertRaises(TypeError) as cm:
                dlb.ex.Context.find_path_in('a', 'abc')
            self.assertEqual(msg, str(cm.exception))

            with self.assertRaises(TypeError) as cm:
                dlb.ex.Context.find_path_in('a', b'abc')
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_non_directory(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.find_path_in('a', [dlb.fs.Path('/x')])
            self.assertEqual("not a directory: '/x'", str(cm.exception))

    def test_none_for_empty(self):
        with dlb.ex.Context():
            self.assertIsNone(dlb.ex.Context.find_path_in('a', []))

    def test_none_if_not_found(self):
        self.assertFalse(os.path.exists('/not/existing/path'))
        with dlb.ex.Context():
            self.assertIsNone(dlb.ex.Context.find_path_in('a', ['/not/existing/path/']))

    def test_finds_first(self):
        os.makedirs('d/a/b')
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('a/b/', ['c/', 'd/', 'e/'])
            self.assertEqual(dlb.ex.Context.root_path / 'd/a/b/', p)

    def test_makes_relative_to_working_tree_root(self):
        os.mkdir('x')
        os.makedirs('d/a/b')
        with dlb.ex.Context():
            with tools_for_test.DirectoryChanger('x'):
                p = dlb.ex.Context().find_path_in('a/b/', ['d/'])
            self.assertEqual(dlb.ex.Context.root_path / 'd/a/b/', p)

    def test_finds_only_directory_for_directory(self):
        os.makedirs('d/')
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('d/', ['.'])
            self.assertEqual(dlb.ex.Context.root_path / 'd/', p)
            p = dlb.ex.Context().find_path_in('d', ['.'])
            self.assertIsNone(p)

    def test_finds_only_nondirectory_for_nondirectory(self):
        with open('d', 'xb'):
            pass
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('d', ['.'])
            self.assertEqual(dlb.ex.Context.root_path / 'd', p)
            p = dlb.ex.Context().find_path_in('d/', ['.'])
            self.assertIsNone(p)


class ExplicitHelperTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_relative_path_is_relative_to_working_tree_root(self):
        with dlb.ex.Context():
            dlb.ex.Context.helper['a/b'] = 'x'
            self.assertEqual(dlb.ex.Context.root_path / 'x', dlb.ex.Context.helper[dlb.fs.Path('a/b')])

    def test_assigned_can_be_modified_and_deleted(self):
        with dlb.ex.Context():
            dlb.ex.Context.helper['a/b'] = '/x'
            self.assertEqual(dlb.fs.Path('/x'), dlb.ex.Context.helper[dlb.fs.Path('a/b')])
            dlb.ex.Context.helper['a/b'] = '/u/v'
            self.assertEqual(dlb.fs.Path('/u/v'), dlb.ex.Context.helper[dlb.fs.Path('a/b')])

    def test_fails_for_absolute_helper_path(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.helper['/a/b'] = '/x'
            self.assertEqual("'helper_path' must not be absolute", str(cm.exception))

    def test_fails_for_non_matching_isdir(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.helper['a/b/'] = '/x'
            msg = "when 'helper_path' is a directory, 'abs_path' must also be a directory"
            self.assertEqual(msg, str(cm.exception))
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.helper['a/b'] = '/x/'
            msg = "when 'helper_path' is a non-directory, 'abs_path' must also be a non-directory"
            self.assertEqual(msg, str(cm.exception))

    def test_is_not_in_initially(self):
        with dlb.ex.Context():
            self.assertNotIn('a', dlb.ex.Context.active.helper)
            self.assertIsNone(dlb.ex.Context.helper.get('a'))
            with self.assertRaises(KeyError):
                dlb.ex.Context.helper['a']
            dlb.ex.Context.helper[dlb.fs.Path('a')] = '/a'
            self.assertIn('a', dlb.ex.Context.active.helper)

    def test_inner_inherits_outer(self):
        with dlb.ex.Context():
            self.assertNotIn('a', dlb.ex.Context.active.helper)
            dlb.ex.Context.helper['b'] = '/b'
            with dlb.ex.Context():
                dlb.ex.Context.helper['a'] = '/a'
                self.assertIn('b', dlb.ex.Context.active.helper)
            self.assertIn('b', dlb.ex.Context.active.helper)

    def test_inner_does_not_change_outer(self):
        with dlb.ex.Context():
            dlb.ex.Context.helper['b'] = '/b'

            with dlb.ex.Context():
                dlb.ex.Context.helper['a'] = '/a'
                dlb.ex.Context.helper['b'] = '/B'
                self.assertEqual(dlb.fs.Path('/B'), dlb.ex.Context.helper['b'])

            self.assertNotIn('a', dlb.ex.Context.active.helper)
            self.assertEqual(dlb.fs.Path('/b'), dlb.ex.Context.active.helper['b'])

    def test_is_dictionarylike(self):
        with dlb.ex.Context():
            dlb.ex.Context.helper['ls'] = '/ls'
            dlb.ex.Context.helper['gcc'] = '/gcc'
            items = [i for i in dlb.ex.Context.helper.items()]
            self.assertEqual([
                (dlb.fs.Path('gcc'), dlb.fs.Path('/gcc')),
                (dlb.fs.Path('ls'), dlb.ex.Context.helper['ls'])
            ], sorted(items))
            self.assertEqual(2, len(dlb.ex.Context.active.helper))
            keys = [k for k in dlb.ex.Context.active.helper]
            self.assertEqual([dlb.fs.Path('gcc'), dlb.fs.Path('ls')], sorted(keys))

    def test_has_repr(self):
        with dlb.ex.Context():
            dlb.ex.Context.helper['ls'] = '/ls'
            dlb.ex.Context.helper['gcc'] = '/gcc'
            s = repr(dlb.ex.Context.helper)
            self.assertEqual("HelperDict({'gcc': '/gcc', 'ls': '/ls'})", s)

    def test_assignment_fails_on_inactive_context(self):
        with dlb.ex.Context() as c0:
            helper0 = c0.helper
            with dlb.ex.Context():
                regex = (
                    r"(?m)\A"
                    r"'helper' of an inactive context must not be modified\n"
                    r"  \| use 'dlb\.ex\.Context\.active\.helper' to get 'helper' of the active context\Z"
                )
                with self.assertRaisesRegex(dlb.ex.context.ContextModificationError, regex):
                    helper0['a'] = '/a'


@unittest.skipIf(not os.path.isfile('/bin/ls'), 'requires ls')
class ImplicitHelperTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_implicit_in_inner_affects_outer(self):
        with dlb.ex.Context(find_helpers=True):

            with dlb.ex.Context(find_helpers=True):
                p = dlb.ex.Context.helper['ls']
                q = dlb.ex.Context.find_path_in('ls')
                self.assertEqual(q, p)

            p = dlb.ex.Context.helper['ls']
            self.assertEqual(q, p)
            self.assertIn('ls', dlb.ex.Context.active.helper)

    def test_inner_fails_if_root_context_explicit_only(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                with dlb.ex.Context(find_helpers=True):
                    pass
            msg = "'find_helpers' must be False if 'find_helpers' of root context is False"
            self.assertEqual(msg, str(cm.exception))

    def test_is_dictionarylike(self):
        with dlb.ex.Context(find_helpers=True):
            dlb.ex.Context.helper['ls']
            with dlb.ex.Context(find_helpers=True):
                dlb.ex.Context.helper['ls'] = dlb.ex.Context.helper['ls']
                dlb.ex.Context.helper['gcc'] = '/gcc'
                items = [i for i in dlb.ex.Context.helper.items()]
                self.assertEqual([
                    (dlb.fs.Path('gcc'), dlb.fs.Path('/gcc')),
                    (dlb.fs.Path('ls'), dlb.ex.Context.helper['ls'])
                ], sorted(items))
                self.assertEqual(2, len(dlb.ex.Context.active.helper))
                keys = [k for k in dlb.ex.Context.active.helper]
                self.assertEqual([dlb.fs.Path('gcc'), dlb.fs.Path('ls')], sorted(keys))

    def test_has_repr(self):
        with dlb.ex.Context(find_helpers=True):
            dlb.ex.Context.helper['ls'] = '/ls'
            dlb.ex.Context.helper['gcc'] = '/gcc'
            s = repr(dlb.ex.Context.helper)
            self.assertEqual("HelperDict({'gcc': '/gcc', 'ls': '/ls'})", s)
