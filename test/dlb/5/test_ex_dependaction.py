# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import dlb.ex._toolrun
import dlb.ex._dependaction
import os.path
import io
import asyncio
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class BrokenReplaceDirectoryOutputTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_creates_nonexistent_destination_directory(self):
        del dlb.ex._dependaction.DirectoryOutputAction.replace_filesystem_object

        with dlb.ex.Context() as c:
            action = dlb.ex._dependaction.DirectoryOutputAction(dlb.ex.output.Directory(), 'test_directory')
            rd = dlb.ex._toolrun.RedoContext(c, {dlb.fs.Path('x/y/a/'): action})
            os.makedirs('u/v')

            with self.assertRaises(ValueError) as cm:
                rd.replace_output('x/y/a/', 'u/')
            self.assertEqual('do not know how to replace', str(cm.exception))
