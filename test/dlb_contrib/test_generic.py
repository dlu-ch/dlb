# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import dlb_contrib.generic
import os.path
import os
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class CheckTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_scenario1(self):
        class ATool(dlb.ex.Tool):
            async def redo(self, result, context):
                pass

        open('a.txt', 'xb').close()
        os.mkdir('b')

        with dlb.ex.Context():
            check = dlb_contrib.generic.Check(input_files=['a.txt'], input_directories=['b/'])
            self.assertTrue(ATool().start(force_redo=check.start()))
            self.assertFalse(ATool().start(force_redo=check.start()))

            with open('a.txt', 'wb') as f:
                f.write(b'0')

            self.assertTrue(ATool().start(force_redo=check.start()))
            self.assertFalse(ATool().start(force_redo=check.start()))

            os.mkdir(os.path.join('b', 'c'))
            self.assertTrue(ATool().start(force_redo=check.start()))
            self.assertFalse(ATool().start(force_redo=check.start()))


class CheckResultTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_scenario1(self):
        t = dlb_contrib.generic.Check(result_file='build/out/r')

        with dlb.ex.Context():
            r = t.start()  # usually with force_redo=...
            self.assertTrue(r)
            if r:
                self.assertFalse(r.result_file.native.raw.exists())
                # ... perform the actual task
                self.assertTrue(r.result_file[:-1].native.raw.is_dir())
                r.result_file.native.raw.touch()  # mark as completed

        with dlb.ex.Context():
            r = t.start()
            self.assertFalse(r)

        with dlb.ex.Context():
            r = t.start(force_redo=True)
            self.assertTrue(r)
            if r:
                self.assertTrue(r.result_file[:-1].native.raw.is_dir())
                self.assertFalse(r.result_file.native.raw.exists())
                r.result_file.native.raw.touch()  # mark as completed


class VersionWordTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_matches_space_delimited_version_word(self):
        self.assertEqual(b'1.2.3', dlb_contrib.generic.VERSION_WORD_REGEX.search(b' 1.2.3').group('version'))
        self.assertEqual(b'v1.2.3-alpha4',
                         dlb_contrib.generic.VERSION_WORD_REGEX.search(b'v1.2.3-alpha4 ').group('version'))
        self.assertTrue(b'ver1.2.3-456f+h_e@4',
                        dlb_contrib.generic.VERSION_WORD_REGEX.search(b' \vver1.2.3-456f+h_e@4\t ').group('version'))
        self.assertTrue(b'8.30',
                        dlb_contrib.generic.VERSION_WORD_REGEX.search(b'ls (GNU coreutils) 8.30').group('version'))

    def test_does_not_match_nonspace_delimited_version_word(self):
        self.assertIsNone(dlb_contrib.generic.VERSION_WORD_REGEX.search(b'\xFF1.2.3'))
        self.assertIsNone(dlb_contrib.generic.VERSION_WORD_REGEX.search(b'1.2.3\xFF'))


class EmptyVersionQueryTest(testenv.TemporaryWorkingDirectoryTestCase):
    def test_is_empty(self):
        with dlb.ex.Context():
            version_by_path = dlb_contrib.generic.VersionQuery().start().version_by_path
        self.assertEqual({}, version_by_path)


@unittest.skipIf(not os.path.isfile('/bin/ls'), 'requires ls')
class LsVersionQueryTest(testenv.TemporaryWorkingDirectoryTestCase):
    def test_ls(self):
        class VersionQuery(dlb_contrib.generic.VersionQuery):
            VERSION_PARAMETERS_BY_EXECUTABLE = {
                'ls': ('--version',)
            }

        with dlb.ex.Context():
            version_by_path = VersionQuery().start().version_by_path

        self.assertEqual([dlb.fs.Path('/bin/ls')], sorted(version_by_path.keys()))
        self.assertRegex(version_by_path[dlb.fs.Path('/bin/ls')], r'[0-9]+(\.[0-9]+)+')
