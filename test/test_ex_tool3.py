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
import unittest
import tools_for_test


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()
    log_file = dlb.ex.Tool.Output.RegularFile(required=False, explicit=False)
    include_directories = dlb.ex.Tool.Input.Directory[:](required=False)

    def redo(self):
        dlb.di.inform("redoing right now")


class RunWithMissingExplicitInputDependencyTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_inexisting_inputfile(self):
        os.mkdir('.dlbroot')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.out', include_directories=['src/serdes/'])
                t.run()
        msg = "input dependency 'source_file' contains a path of an non-existing filesystem object: 'src/a.cpp'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_inaccessible_inputfile(self):
        os.mkdir('.dlbroot')
        os.mkdir('src')
        os.chmod('src', 0o000)
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='out/a.out', include_directories=['src/serdes/'])
                t.run()
        regex = (
            r"(?m)\A"
            r"input dependency 'source_file' contains a path of an inaccessible filesystem object: 'src/a.cpp'\n"
            r"  \| reason: .*\Z"
        )
        self.assertRegex(str(cm.exception), regex)
        os.chmod('src', 0o600)

    def test_fails_for_nonnormalized_inputfile_path(self):
        os.mkdir('.dlbroot')
        with self.assertRaises(dlb.ex.DependencyCheckError) as cm:
            with dlb.ex.Context():
                t = ATool(source_file='../a.cpp', object_file='out/a.out', include_directories=['src/serdes/'])
                t.run()
        msg = (
            "input dependency 'source_file' contains a path that is not a managed tree path: '../a.cpp'\n"
            "  | reason: is an upwards path: '../a.cpp'"
        )
        self.assertEqual(msg, str(cm.exception))


class RunTwiceTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_fails_for_nonnormalized_inputfile_path(self):
        os.mkdir('.dlbroot')
        os.mkdir('src')
        with open('src/a.cpp', 'xb'):
            pass

        for i in range(2):
            with dlb.ex.Context():
                t = ATool(source_file='src/a.cpp', object_file='a.out')
                t.run()
