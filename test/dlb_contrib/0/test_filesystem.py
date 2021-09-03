# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import dlb_contrib.filesystem
import sys
import os.path
import os
import errno
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class HardlinkOrCopyTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_succeed(self):
        open('a', 'x').close()
        used_hardlink = dlb_contrib.filesystem.hardlink_or_copy(src='a', dst='o')
        self.assertEqual(used_hardlink, os.path.samefile('a', 'o'))

    def test_uses_hardlink_or_fails_when_requested(self):
        open('a', 'x').close()
        try:
            used_hardlink = dlb_contrib.filesystem.hardlink_or_copy(src='a', dst='o', use_hard_link=True)
            self.assertTrue(used_hardlink)
        except PermissionError:
            pass

    def test_copies_when_requested(self):
        open('a', 'x').close()
        used_hardlink = dlb_contrib.filesystem.hardlink_or_copy(src='a', dst='o', use_hard_link=False)
        self.assertFalse(used_hardlink)

    @unittest.skipIf(sys.platform == 'win32', 'POSIX filesystem only')
    def test_fails_if_target_inaccessible(self):
        os.mkdir('d')
        open('a', 'x').close()
        try:
            os.chmod('d', 0x000)  # -> EACCES
            with self.assertRaises(PermissionError) as cm:
                dlb_contrib.filesystem.hardlink_or_copy(src='a', dst=os.path.join('d', 'o'))
            self.assertEqual(errno.EACCES, cm.exception.errno)
        finally:
            os.chmod('d', 0o777)

    def test_fails_for_directory(self):
        os.mkdir('d')
        with self.assertRaises(RuntimeError) as cm:
            dlb_contrib.filesystem.hardlink_or_copy(src='d', dst='o')
        self.assertEqual("not a regular file: 'd'", str(cm.exception))

    def test_fails_for_symbolic_link(self):
        open('f', 'wb').close()
        try:
            os.symlink('f', 's', target_is_directory=False)
            self.assertTrue(os.path.islink('s'))
        except OSError:  # on platform or filesystem that does not support symlinks
            self.assertNotEqual(os.name, 'posix', 'on any POSIX system, symbolic links should be supported')
            raise unittest.SkipTest from None

        with self.assertRaises(RuntimeError) as cm:
            dlb_contrib.filesystem.hardlink_or_copy(src='s', dst='o')
        self.assertEqual("not a regular file: 's'", str(cm.exception))


class FileCollectorTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_creates_directory(self):
        with dlb.ex.Context():
            r = dlb_contrib.filesystem.FileCollector(input_files=[], output_directory='build/out/c/').start()
        self.assertTrue(r.output_directory.native.raw.is_dir())

    def test_directory_contains_all(self):
        os.mkdir('c')
        open('a', 'x').close()
        open('b', 'x').close()
        open(os.path.join('c', 'd'), 'x').close()

        with dlb.ex.Context():
            r = dlb_contrib.filesystem.FileCollector(
                input_files=['a', 'b', 'c/d'],
                output_directory='build/out/'
            ).start()
        self.assertEqual(['a', 'b', 'd'], r.output_directory.list_r())

    def test_replaces_existing(self):
        os.makedirs(os.path.join('build', 'out', 'x'))
        open('a', 'x').close()
        open('b', 'x').close()

        with dlb.ex.Context():
            r = dlb_contrib.filesystem.FileCollector(
                input_files=['a', 'b'],
                output_directory='build/out/'
            ).start()
        self.assertEqual(['a', 'b'], r.output_directory.list_r())

    def test_fails_for_duplicate_filename(self):
        os.mkdir('c')
        open('a', 'x').close()
        open('b', 'x').close()
        open(os.path.join('c', 'a'), 'x').close()

        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                dlb_contrib.filesystem.FileCollector(
                    input_files=['a', 'b', 'c/a'],
                    output_directory='build/out/'
                ).start()
        self.assertEqual("'input_files' contains multiple members with same file name: 'a' and 'c/a'",
                         str(cm.exception))
