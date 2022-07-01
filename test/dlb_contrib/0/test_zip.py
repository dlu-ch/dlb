# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import dlb_contrib.zip
import sys
import os.path
import zipfile
import testtool
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
            self.assertEqual([], z.namelist())

    def test_nonempty_directory(self):
        os.mkdir('d')
        os.mkdir(os.path.join('d', 'a'))
        open(os.path.join('d', 'a', 'b'), 'xb').close()
        open(os.path.join('d', 'c'), 'xb').close()
        os.mkdir(os.path.join('d', 'e'))  # this will be ignored since it is empty
        os.makedirs(os.path.join('d', 'f', 'g'))
        open(os.path.join('d', 'f', 'g', 'h'), 'xb').close()

        with dlb.ex.Context():
            dlb_contrib.zip.ZipDirectory(
                content_directory='d/',
                archive_file='a.bzip').start()
        with dlb.ex.Context(), dlb.ex.Context.active.temporary(is_dir=True) as t:
            with zipfile.ZipFile('a.bzip', 'r') as z:
                self.assertEqual(['a/', 'f/', 'f/g/', 'a/b', 'c', 'f/g/h'], z.namelist())
                z.extractall(t.native)
                self.assertTrue((t / 'a/b').native.raw.is_file())
                self.assertTrue((t / 'c').native.raw.is_file())


class ZipDirectoryWithOutPrefixDirectories(dlb_contrib.zip.ZipDirectory):
    INCLUDE_PREFIX_DIRECTORIES = False


class ZipDirectoryWithoutPrefixDirectoriesTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_empty_directory(self):
        os.mkdir('d')
        with dlb.ex.Context():
            ZipDirectoryWithOutPrefixDirectories(
                content_directory='d/',
                archive_file='a.bzip').start()
        with zipfile.ZipFile('a.bzip', 'r') as z:
            self.assertEqual([], z.namelist())

    def test_nonempty_directory(self):
        os.mkdir('d')
        os.mkdir(os.path.join('d', 'a'))
        open(os.path.join('d', 'a', 'b'), 'xb').close()
        open(os.path.join('d', 'c'), 'xb').close()
        os.mkdir(os.path.join('d', 'e'))  # this will be ignored since it is empty
        os.makedirs(os.path.join('d', 'f', 'g'))
        open(os.path.join('d', 'f', 'g', 'h'), 'xb').close()

        with dlb.ex.Context():
            ZipDirectoryWithOutPrefixDirectories(
                content_directory='d/',
                archive_file='a.bzip').start()
        with dlb.ex.Context(), dlb.ex.Context.active.temporary(is_dir=True) as t:
            with zipfile.ZipFile('a.bzip', 'r') as z:
                self.assertEqual(['a/b', 'c', 'f/g/h'], z.namelist())
                z.extractall(t.native)
                self.assertTrue((t / 'a/b').native.raw.is_file())
                self.assertTrue((t / 'c').native.raw.is_file())


@unittest.skipUnless(sys.platform != 'win32', 'requires POSIX filesystem')
class ZipDirectorySpecialTest(testenv.TemporaryWorkingDirectoryTestCase):
    def test_filename_with_backslash(self):
        os.mkdir('d')
        open(os.path.join('d', 'a\\b'), 'xb').close()

        with dlb.ex.Context():
            dlb_contrib.zip.ZipDirectory(
                content_directory='d/',
                archive_file='a.bzip').start()
        with dlb.ex.Context(), dlb.ex.Context.active.temporary(is_dir=True) as t:
            with zipfile.ZipFile('a.bzip', 'r') as z:
                self.assertEqual(['a\\b'], z.namelist())
                z.extractall(t.native)
                self.assertTrue((t / 'a\\b').native.raw.is_file())

    def test_does_not_follow_symlink(self):
        os.mkdir('d')
        open(os.path.join('d', 'a'), 'xb').close()
        os.mkdir('d2')
        open(os.path.join('d2', 'c'), 'xb').close()
        testtool.symlink_or_skip('../d2/', os.path.join('d', 'b'), target_is_directory=True)

        with dlb.ex.Context():
            dlb_contrib.zip.ZipDirectory(
                content_directory='d/',
                archive_file='a.bzip').start()
        with zipfile.ZipFile('a.bzip', 'r') as z:
            self.assertEqual(['a'], z.namelist())
