# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import sys
import dlb.ex
import dlb_contrib.msbatch
import unittest


class PathTest(unittest.TestCase):
    def test_fails_without_bat_suffix(self):
        dlb_contrib.msbatch.BatchFilePath('a.bat')
        dlb_contrib.msbatch.BatchFilePath('a.bAt')

        with self.assertRaises(ValueError):
            dlb_contrib.msbatch.BatchFilePath('a')
        with self.assertRaises(ValueError):
            dlb_contrib.msbatch.BatchFilePath('.bat')
        with self.assertRaises(ValueError):
            dlb_contrib.msbatch.BatchFilePath('..bat')


@unittest.skipIf(sys.platform != 'win32', 'requires MS Windows')
class BatchFileTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_batchfile_is_found(self):

        for file_name in ['a.bat', 'a b.bat', 'a^b.bat', 'a ^b.bat', '统一码.bat']:
            with open(file_name, 'x', encoding='ascii') as f:
                f.write('cd %1\n\r')
                f.write('echo {"a": "b"} > env.json\n\r')
            with dlb.ex.Context():
                env = dlb_contrib.msbatch.RunEnvBatch(batch_file='a.bat').run().environment
            self.assertEqual({'a': 'b'}, env)

    def test_fails_without_envvar_file(self):
        open('a.bat', 'x').close()
        with self.assertRaises(Exception) as cm:
            with dlb.ex.Context():
                dlb_contrib.msbatch.RunEnvBatch(batch_file='a.bat').run()
        msg = (
            "exported environment file not found: 'env.json'\n"
            "  | create it in the batch file with 'python3 -m dlb_contrib.exportenv'"
        )
        self.assertEqual(msg, str(cm.exception))
