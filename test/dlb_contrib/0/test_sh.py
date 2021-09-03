# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.sh
import os.path
import unittest
from typing import Optional, Iterable, Union


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

    source_files = dlb.ex.input.RegularFile[:]()

    def get_scriptlet_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return [s for s in self.source_files]


class OutputThreeLinesIncrementally(dlb_contrib.sh.ShScriptlet):
    SCRIPTLET = """
        echo first
        echo second
        echo third
        """

    def get_chunk_processor(self) -> Optional[dlb.ex.ChunkProcessor]:
        class Processor(dlb.ex.ChunkProcessor):
            def __init__(self):
                self.result = []

            def process(self, chunk: bytes, is_last: bool):
                if b'i' in chunk:
                    self.result.append(chunk)

        return Processor()


class QuoteTest(unittest.TestCase):

    def test_it(self):
        self.assertEqual("''", dlb_contrib.sh.quote(''))
        self.assertEqual("'a\"b'", dlb_contrib.sh.quote('a"b'))
        self.assertEqual("'a'\\''b'", dlb_contrib.sh.quote("a'b"))


@unittest.skipIf(not testenv.has_executable_in_path('sh'), 'requires sh in $PATH')
class ShTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_line_output(self):
        with dlb.ex.Context():
            output = OutputTwoLines().start().processed_output
        self.assertEqual(b'first\nsecond\n', output)

    def test_incremental_line_output(self):
        with dlb.ex.Context():
            output = OutputThreeLinesIncrementally().start().processed_output
        self.assertEqual([b'first', b'third'], output)

    def test_read_files(self):
        with open('a', 'xb') as f:
            f.write(b'aah... ')
        with open('o', 'xb') as f:
            f.write(b'ooh!')

        with dlb.di.Cluster('let sh output all parameters'), dlb.ex.Context():
            output = ReadFile(source_files=['a', 'o']).start().processed_output
            dlb.di.inform(f"scriptlet returned {output!r}")
        self.assertEqual(b"scriptlet\naah... ooh!", output)
