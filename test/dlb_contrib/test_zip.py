# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import dlb_contrib.zip
import os.path
import zipfile
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class ZipDirectoryTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_empty_directory(self):
        os.mkdir('d')
        with dlb.ex.Context():
            dlb_contrib.zip.ZipDirectory(
                content_directory='d/',
                archive_file='a.bzip').start()
        with zipfile.ZipFile('a.bzip', 'r') as z:
            self.assertEqual([], z.filelist)

    def test_nonempty_directory(self):
        os.mkdir('d')
        os.mkdir(os.path.join('d', 'a'))
        open(os.path.join('d', 'a', 'b'), 'xb').close()
        open(os.path.join('d', 'c'), 'xb').close()
        os.mkdir(os.path.join('d', 'e'))  # this will by ignored since it is empty

        with dlb.ex.Context():
            dlb_contrib.zip.ZipDirectory(
                content_directory='d/',
                archive_file='a.bzip').start()
        with dlb.ex.Context(), dlb.ex.Context.temporary(is_dir=True) as t:
            with zipfile.ZipFile('a.bzip', 'r') as z:
                self.assertEqual(['a/b', 'c'], [fi.filename for fi in z.filelist])
                z.extractall(t.native)
                self.assertTrue((t / 'a/b').native.raw.is_file())
                self.assertTrue((t / 'c').native.raw.is_file())


@unittest.skipIf(os.name != 'posix', 'requires POSIX filesystem semantics')
class ZipDirectorySpecialTest(testenv.TemporaryWorkingDirectoryTestCase):
    def test_filename_with_backslash(self):
        os.mkdir('d')
        open(os.path.join('d', 'a\\b'), 'xb').close()

        with dlb.ex.Context():
            dlb_contrib.zip.ZipDirectory(
                content_directory='d/',
                archive_file='a.bzip').start()
        with dlb.ex.Context(), dlb.ex.Context.temporary(is_dir=True) as t:
            with zipfile.ZipFile('a.bzip', 'r') as z:
                self.assertEqual(['a\\b'], [fi.filename for fi in z.filelist])
                z.extractall(t.native)
                self.assertTrue((t / 'a\\b').native.raw.is_file())

    def test_does_not_follow_symlink(self):
        os.mkdir('d')
        open(os.path.join('d', 'a'), 'xb').close()
        os.mkdir('d2')
        open(os.path.join('d2', 'c'), 'xb').close()
        try:
            os.symlink('../d2/', os.path.join('d', 'b'), target_is_directory=True)
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with dlb.ex.Context():
            dlb_contrib.zip.ZipDirectory(
                content_directory='d/',
                archive_file='a.bzip').start()
        with zipfile.ZipFile('a.bzip', 'r') as z:
            self.assertEqual(['a'], [fi.filename for fi in z.filelist])
