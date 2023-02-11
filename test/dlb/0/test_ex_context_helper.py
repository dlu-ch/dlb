# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import os.path
import unittest


class ExecutableSearchPathNotRunningTest(unittest.TestCase):

    def test_fails_if_not_running(self):
        c = dlb.ex.Context()
        with self.assertRaises(dlb.ex.NotRunningError):
            c.executable_search_paths


class ExecutableSearchPathTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_is_nonempty_tuple_of_absolute_paths(self):
        with dlb.ex.Context():
            paths = dlb.ex.Context.active.executable_search_paths

        self.assertIsInstance(paths, tuple)
        self.assertGreater(len(paths), 0)
        for p in paths:
            self.assertIsInstance(p, dlb.fs.Path)
            self.assertTrue(p.is_absolute())

        self.assertEqual(len(set(paths)), len(paths))

    def test_nondirectories_and_nonexistent_paths_are_ignored(self):
        os.mkdir('d')
        open('f', 'xb').close()

        orig_path = os.environ['PATH']
        try:
            os.environ['PATH'] = os.pathsep.join(
                [os.getcwd(), os.path.join(os.getcwd(), 'd'), os.path.join(os.getcwd(), 'f')])
            with dlb.ex.Context():
                paths = dlb.ex.Context.active.executable_search_paths
        finally:
            os.environ['PATH'] = orig_path

        cwd = dlb.fs.Path(dlb.fs.Path.Native(os.getcwd()), is_dir=True)
        self.assertEqual((cwd, cwd / 'd/'), paths)  # same order

    def test_relative_paths_are_relative_to_root_path(self):
        os.mkdir('d')

        orig_path = os.environ['PATH']
        try:
            os.environ['PATH'] = 'd'
            with dlb.ex.Context():
                paths = dlb.ex.Context.active.executable_search_paths
        finally:
            os.environ['PATH'] = orig_path

        cwd = dlb.fs.Path(dlb.fs.Path.Native(os.getcwd()), is_dir=True)
        self.assertEqual((cwd / 'd/',), paths)

    def test_leading_tilde_is_not_expanded(self):
        os.mkdir('d')

        orig_path = os.environ['PATH']
        try:
            os.environ['PATH'] = '~'
            with dlb.ex.Context():
                paths = dlb.ex.Context.active.executable_search_paths
        finally:
            os.environ['PATH'] = orig_path

        self.assertEqual((), paths)

    def test_invalid_paths_are_ignored(self):
        os.mkdir('d')

        orig_path = os.environ['PATH']
        try:
            os.environ['PATH'] = os.pathsep
            with dlb.ex.Context():
                paths = dlb.ex.Context.active.executable_search_paths
            self.assertEqual((), paths)
        finally:
            os.environ['PATH'] = orig_path


class FindPathInTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_absolute(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.active.find_path_in('/a', [])
        self.assertEqual("'path' must not be absolute", str(cm.exception))

    def test_fails_for_str_or_bytes(self):
        msg = "'search_prefixes' must be iterable (other than 'str' or 'bytes')"

        with dlb.ex.Context():
            with self.assertRaises(TypeError) as cm:
                dlb.ex.Context.active.find_path_in('a', 'abc')
            self.assertEqual(msg, str(cm.exception))

            with self.assertRaises(TypeError) as cm:
                dlb.ex.Context.active.find_path_in('a', b'abc')
            self.assertEqual(msg, str(cm.exception))

    def test_fails_for_non_directory(self):
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.active.find_path_in('a', [dlb.fs.Path('/x')])
            self.assertEqual("not a directory: '/x'", str(cm.exception))

    def test_none_for_empty(self):
        with dlb.ex.Context():
            self.assertIsNone(dlb.ex.Context.active.find_path_in('a', []))

    def test_none_if_not_found(self):
        self.assertFalse(os.path.exists('/not/existing/path'))
        with dlb.ex.Context():
            self.assertIsNone(dlb.ex.Context.active.find_path_in('a', ['/not/existing/path/']))

    def test_finds_first(self):
        os.makedirs('d/a/b')
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('a/b/', ['c/', 'd/', 'e/'])
            self.assertEqual(dlb.ex.Context.active.root_path / 'd/a/b/', p)

    def test_makes_relative_to_working_tree_root(self):
        os.mkdir('x')
        os.makedirs('d/a/b')
        with dlb.ex.Context():
            with testenv.DirectoryChanger('x'):
                p = dlb.ex.Context().find_path_in('a/b/', ['d/'])
            self.assertEqual(dlb.ex.Context.active.root_path / 'd/a/b/', p)

    def test_finds_only_directory_for_directory(self):
        os.makedirs('d/')
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('d/', ['.'])
            self.assertEqual(dlb.ex.Context.active.root_path / 'd/', p)
            p = dlb.ex.Context().find_path_in('d', ['.'])
            self.assertIsNone(p)

    def test_finds_only_nondirectory_for_nondirectory(self):
        open('d', 'xb').close()
        with dlb.ex.Context():
            p = dlb.ex.Context().find_path_in('d', ['.'])
            self.assertEqual(dlb.ex.Context.active.root_path / 'd', p)
            p = dlb.ex.Context().find_path_in('d/', ['.'])
            self.assertIsNone(p)


@unittest.skipUnless(os.path.isfile('/bin/ls'), 'requires ls')
class HelperTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_find_helpers_of_none_for_root_mean_true(self):
        with dlb.ex.Context(find_helpers=None):
            self.assertIsNotNone(dlb.ex.Context.active.helper.get('ls'))

    def test_find_helpers_of_none_for_nonroot_mean_value_of_root(self):
        with dlb.ex.Context(find_helpers=True):
            with dlb.ex.Context(find_helpers=None):
                with dlb.ex.Context(find_helpers=None):
                    self.assertIsNotNone(dlb.ex.Context.active.helper.get('ls'))

        with dlb.ex.Context(find_helpers=False):
            with dlb.ex.Context(find_helpers=None):
                with dlb.ex.Context(find_helpers=None):
                    self.assertIsNone(dlb.ex.Context.active.helper.get('ls'))


class ExplicitHelperTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_relative_path_is_relative_to_working_tree_root(self):
        with dlb.ex.Context(find_helpers=False):
            dlb.ex.Context.active.helper['a/b'] = 'x'
            self.assertEqual(dlb.ex.Context.active.root_path / 'x', dlb.ex.Context.active.helper[dlb.fs.Path('a/b')])

    def test_assigned_can_be_modified_and_deleted(self):
        with dlb.ex.Context(find_helpers=False):
            dlb.ex.Context.active.helper['a/b'] = '/x'
            self.assertEqual(dlb.fs.Path('/x'), dlb.ex.Context.active.helper[dlb.fs.Path('a/b')])
            dlb.ex.Context.active.helper['a/b'] = '/u/v'
            self.assertEqual(dlb.fs.Path('/u/v'), dlb.ex.Context.active.helper[dlb.fs.Path('a/b')])

    def test_fails_for_absolute_helper_path(self):
        with dlb.ex.Context(find_helpers=False):
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.active.helper['/a/b'] = '/x'
            self.assertEqual("'helper_path' must not be absolute", str(cm.exception))

    def test_fails_for_non_matching_isdir(self):
        with dlb.ex.Context(find_helpers=False):
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.active.helper['a/b/'] = '/x'
            msg = "when 'helper_path' is a directory, 'abs_path' must also be a directory"
            self.assertEqual(msg, str(cm.exception))
            with self.assertRaises(ValueError) as cm:
                dlb.ex.Context.active.helper['a/b'] = '/x/'
            msg = "when 'helper_path' is a non-directory, 'abs_path' must also be a non-directory"
            self.assertEqual(msg, str(cm.exception))

    def test_is_not_in_initially(self):
        with dlb.ex.Context(find_helpers=False):
            self.assertNotIn('a', dlb.ex.Context.active.helper)
            self.assertIsNone(dlb.ex.Context.active.helper.get('a'))
            with self.assertRaises(KeyError) as cm:
                dlb.ex.Context.active.helper['a']
            self.assertEqual(
                repr("not a known dynamic helper in the context: 'a'\n"
                     "  | use 'dlb.ex.Context.active.helper[...] = ...'"),
                str(cm.exception))
            dlb.ex.Context.active.helper[dlb.fs.Path('a')] = '/a'
            self.assertIn('a', dlb.ex.Context.active.helper)

    def test_inner_inherits_outer(self):
        with dlb.ex.Context(find_helpers=False):
            self.assertNotIn('a', dlb.ex.Context.active.helper)
            dlb.ex.Context.active.helper['b'] = '/b'
            with dlb.ex.Context(find_helpers=False):
                dlb.ex.Context.active.helper['a'] = '/a'
                self.assertIn('b', dlb.ex.Context.active.helper)
            self.assertIn('b', dlb.ex.Context.active.helper)

    def test_inner_does_not_change_outer(self):
        with dlb.ex.Context(find_helpers=False):
            dlb.ex.Context.active.helper['b'] = '/b'

            with dlb.ex.Context(find_helpers=False):
                dlb.ex.Context.active.helper['a'] = '/a'
                dlb.ex.Context.active.helper['b'] = '/B'
                self.assertEqual(dlb.fs.Path('/B'), dlb.ex.Context.active.helper['b'])

            self.assertNotIn('a', dlb.ex.Context.active.helper)
            self.assertEqual(dlb.fs.Path('/b'), dlb.ex.Context.active.helper['b'])

    def test_is_dictionarylike(self):
        with dlb.ex.Context(find_helpers=False):
            dlb.ex.Context.active.helper['ls'] = '/ls'
            dlb.ex.Context.active.helper['gcc'] = '/gcc'
            items = [i for i in dlb.ex.Context.active.helper.items()]
            self.assertEqual([
                (dlb.fs.Path('gcc'), dlb.fs.Path('/gcc')),
                (dlb.fs.Path('ls'), dlb.ex.Context.active.helper['ls'])
            ], sorted(items))
            self.assertEqual(2, len(dlb.ex.Context.active.helper))
            keys = [k for k in dlb.ex.Context.active.helper]
            self.assertEqual([dlb.fs.Path('gcc'), dlb.fs.Path('ls')], sorted(keys))

    def test_has_repr(self):
        with dlb.ex.Context(find_helpers=False):
            dlb.ex.Context.active.helper['ls'] = '/ls'
            dlb.ex.Context.active.helper['gcc'] = '/gcc'
            s = repr(dlb.ex.Context.active.helper)
            self.assertEqual("HelperDict({'gcc': '/gcc', 'ls': '/ls'})", s)

    def test_assignment_fails_on_inactive_context(self):
        with dlb.ex.Context(find_helpers=False) as c0:
            helper0 = c0.helper
            with dlb.ex.Context(find_helpers=False):
                regex = (
                    r"(?m)\A"
                    r"'helper' of an inactive context must not be modified\n"
                    r"  \| use 'dlb\.ex\.Context\.active\.helper' to get 'helper' of the active context\Z"
                )
                with self.assertRaisesRegex(dlb.ex._error.ContextModificationError, regex):
                    helper0['a'] = '/a'


@unittest.skipUnless(os.path.isfile('/bin/ls'), 'requires ls')
class ImplicitHelperTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_implicit_in_inner_affects_outer(self):
        with dlb.ex.Context(find_helpers=True):

            with dlb.ex.Context(find_helpers=True):
                p = dlb.ex.Context.active.helper['ls']
                q = dlb.ex.Context.active.find_path_in('ls')
                self.assertEqual(q, p)

            p = dlb.ex.Context.active.helper['ls']
            self.assertEqual(q, p)
            self.assertIn('ls', dlb.ex.Context.active.helper)

    def test_inner_fails_if_root_context_explicit_only(self):
        with dlb.ex.Context(find_helpers=False):
            with self.assertRaises(ValueError) as cm:
                with dlb.ex.Context(find_helpers=True):
                    pass
            msg = "'find_helpers' must be False if 'find_helpers' of root context is False"
            self.assertEqual(msg, str(cm.exception))

    def test_is_dictionarylike(self):
        with dlb.ex.Context():
            dlb.ex.Context.active.helper['ls']
            with dlb.ex.Context():
                dlb.ex.Context.active.helper['ls'] = dlb.ex.Context.active.helper['ls']
                dlb.ex.Context.active.helper['gcc'] = '/gcc'
                items = [i for i in dlb.ex.Context.active.helper.items()]
                self.assertEqual([
                    (dlb.fs.Path('gcc'), dlb.fs.Path('/gcc')),
                    (dlb.fs.Path('ls'), dlb.ex.Context.active.helper['ls'])
                ], sorted(items))
                self.assertEqual(2, len(dlb.ex.Context.active.helper))
                keys = [k for k in dlb.ex.Context.active.helper]
                self.assertEqual([dlb.fs.Path('gcc'), dlb.fs.Path('ls')], sorted(keys))

    def test_has_repr(self):
        with dlb.ex.Context():
            dlb.ex.Context.active.helper['ls'] = '/ls'
            dlb.ex.Context.active.helper['gcc'] = '/gcc'
            s = repr(dlb.ex.Context.active.helper)
            self.assertEqual("HelperDict({'gcc': '/gcc', 'ls': '/ls'})", s)
