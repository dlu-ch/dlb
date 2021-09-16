# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import sys
import os.path
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class ExecutableSearchPathTest(testenv.TemporaryDirectoryTestCase):

    def test_invalid_paths_are_ignored(self):
        self.assertNotIn('dlb', sys.modules)
        import dlb.fs

        class NoXxxPath(dlb.fs.Path):
            def check_restriction_to_base(self, components_checked: bool):
                if not components_checked and 'xxx' in self.components[-1:]:
                    raise ValueError("last component must not be 'xxx'")

        orig_path = os.environ['PATH']
        orig_dlb_fs_path = dlb.fs.Path

        try:
            os.environ['PATH'] = f'a{os.pathsep}xxx{os.pathsep}b{os.pathsep}'

            dlb.fs.Path = NoXxxPath
            with self.assertRaises(ValueError):
                dlb.fs.Path.Native('xxx')
            dlb.fs.Path.Native(os.path.join(os.getcwd(), 'xxx', 'a'))  # valid

            os.mkdir('.dlbroot')
            os.mkdir('a')
            os.mkdir('xxx')
            os.mkdir('b')

            import dlb.ex
            with dlb.ex.Context():
                paths = dlb.ex.Context.active.executable_search_paths

            self.assertEqual(['a', 'b'], [p.parts[-1] for p in paths])
        finally:
            dlb.fs.Path = orig_dlb_fs_path
            os.environ['PATH'] = orig_path
