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
import pathlib
import logging
import unittest
import cProfile
import pstats
import tools_for_test


included_files = [f"a{i}.h" for i in range(20)]


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

    def redo(self, result, context):
        with self.object_file.native.raw.open('xb'):
            pass
        result.included_files = included_files


class RunBenchmark(tools_for_test.TemporaryDirectoryTestCase):

    def test_scenario1(self):

        pathlib.Path('.dlbroot').mkdir()
        for p in included_files + ['a.cpp']:
            with pathlib.Path(p).open('xb'):
                pass

        profile = cProfile.Profile()
        profile.enable()

        with dlb.ex.Context():

            dlb.di.set_threshold_level(logging.WARNING)

            t = ATool(source_file='a.cpp', object_file='a.o')
            assert t.run() is not None
            assert t.run() is not None

            for i in range(1000):
                t = ATool(source_file='a.cpp', object_file='a.o')
                assert t.run() is None

        profile.disable()
        stats = pstats.Stats(profile).sort_stats(pstats.SortKey.CUMULATIVE)
        stats.print_stats()

        # e.g. for https://jiffyclub.github.io/snakeviz/
        assert os.path.isabs(__file__)
        stats.dump_stats('{}-{}-{}.prof'.format(__file__, self.__class__.__name__, 'scenario1'))
