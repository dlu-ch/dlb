# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.ex._worktree
import os.path
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class RemoveFilesystemObjectTest(testenv.TemporaryDirectoryTestCase):

    def test_ignores_concurrently_removed_directory(self):
        os.mkdir('x')

        orig_rmdir = os.rmdir

        def raise_file_not_found(path):
            orig_rmdir(path)
            raise FileNotFoundError(path)

        try:
            os.rmdir = raise_file_not_found
            dlb.ex._worktree.remove_filesystem_object(os.path.realpath('x'))
            self.assertFalse(os.path.exists('x'))
        finally:
            os.rmdir = orig_rmdir
