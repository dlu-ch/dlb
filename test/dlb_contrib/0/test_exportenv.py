# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb_contrib.exportenv
import os
import os.path
import json
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class ExportTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_export_creates_file(self):
        dlb_contrib.exportenv.export()
        self.assertTrue(os.path.isfile(dlb_contrib.exportenv.FILE_NAME))

    def test_roundtrip_is_lossless(self):
        os.environ['ö统一码ü'] = ' x\r统一码\ny '
        before = {k: v for k, v in os.environ.items()}
        dlb_contrib.exportenv.export()
        after = dlb_contrib.exportenv.read_exported()
        self.assertEqual(before, after)

    def test_fails_if_exists(self):
        open(dlb_contrib.exportenv.FILE_NAME, 'x').close()
        with self.assertRaises(FileExistsError):
            dlb_contrib.exportenv.export()

    def test_fails_if_not_dict(self):

        open(dlb_contrib.exportenv.FILE_NAME, 'x').close()
        with self.assertRaises(json.decoder.JSONDecodeError):
            dlb_contrib.exportenv.read_exported()

        with open(dlb_contrib.exportenv.FILE_NAME, 'w') as f:
            json.dump([], f)
        with self.assertRaises(TypeError):
            dlb_contrib.exportenv.read_exported()

        with open(dlb_contrib.exportenv.FILE_NAME, 'w') as f:
            json.dump({'1': 2}, f)
        with self.assertRaises(TypeError):
            dlb_contrib.exportenv.read_exported()
