# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.sh
import unittest
from typing import Iterable, Union
import tools_for_test


class OutputTwoLines(dlb_contrib.sh.ShScriptlet):
    SCRIPTLET = """
        echo first
        echo second
        """


class ReadFile(dlb_contrib.sh.ShScriptlet):
    SCRIPTLET = """
        echo $0
        cat -- "$@"
        """

    source_files = dlb.ex.Tool.Input.RegularFile[:]()

    def get_scriptlet_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return [s for s in self.source_files]


@unittest.skipIf(not os.path.isfile('/bin/sh'), 'requires sh')
class ShTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_line_output(self):
        with dlb.ex.Context():
            output = OutputTwoLines().run().output
        self.assertEqual('first\nsecond\n', output)

    def test_read_files(self):
        with open('a', 'xb') as f:
            f.write(b'aah... ')
        with open('o', 'xb') as f:
            f.write(b'ooh!')

        with dlb.di.Cluster('let sh output all parameters'), dlb.ex.Context():
            output = ReadFile(source_files=['a', 'o']).run().output
            dlb.di.inform(f"scriptlet returned {output!r}")
        self.assertEqual("scriptlet\naah... ooh!", output)
