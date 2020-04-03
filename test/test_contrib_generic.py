# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex
import dlb_contrib.generic
import os
import unittest
import tools_for_test


class CheckTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_scenario1(self):
        class ATool(dlb.ex.Tool):
            async def redo(self, result, context):
                pass

        open('a.txt', 'xb').close()
        os.mkdir('b')

        with dlb.ex.Context():
            check = dlb_contrib.generic.Check(input_files=['a.txt'], input_directories=['b/'])
            self.assertTrue(ATool().run(force_redo=check.run()))
            self.assertFalse(ATool().run(force_redo=check.run()))

            with open('a.txt', 'wb') as f:
                f.write(b'0')

            self.assertTrue(ATool().run(force_redo=check.run()))
            self.assertFalse(ATool().run(force_redo=check.run()))

            os.mkdir(os.path.join('b', 'c'))
            self.assertTrue(ATool().run(force_redo=check.run()))
            self.assertFalse(ATool().run(force_redo=check.run()))
