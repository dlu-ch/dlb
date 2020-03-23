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
import cProfile
import pstats
import unittest
import tools_for_test


included_files = [f"a{i}.h" for i in range(20)]


class ATool(dlb.ex.Tool):
    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

    async def redo(self, result, context):
        with (context.root_path / self.object_file).native.raw.open('wb'):
            pass
        result.included_files = included_files


def dump_profile_stats(profile, test_case: unittest.TestCase, result_index: int):
    stats = pstats.Stats(profile).sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats(5)

    assert os.path.isabs(__file__)
    dir_path, file_name = os.path.split(__file__)

    output_dir_path = os.path.join(dir_path, '..', 'out', 'prof')
    file_name = '{}-{}-{}.prof'.format(file_name, test_case.__class__.__name__, result_index)

    os.makedirs(output_dir_path, exist_ok=True)
    stats.dump_stats(os.path.join(output_dir_path, file_name))
    # e.g. for https://jiffyclub.github.io/snakeviz/


class RunBenchmark(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_scenario1(self):
        for p in included_files + ['a.cpp']:
            open(p, 'xb').close()

        profile = cProfile.Profile()

        with dlb.ex.Context():

            dlb.di.set_threshold_level(dlb.di.WARNING)

            t = ATool(source_file='a.cpp', object_file='a.o')
            assert t.run()
            assert t.run()

            profile.enable()

            for i in range(1000):
                t = ATool(source_file='a.cpp', object_file='a.o')
                assert not t.run()

            profile.disable()

        dump_profile_stats(profile, self, 1)


class ImportantRunExecutionPathBenchmark(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_read_filesystem_object_memo_from_path(self):
        import dlb.ex.worktree

        os.makedirs(os.path.join('a', 'b'))
        open(os.path.join('a', 'b', 'c'), 'xb').close()

        dlb.di.set_threshold_level(dlb.di.WARNING)
        p = dlb.fs.Path('a/b/c')

        profile = cProfile.Profile()

        with dlb.ex.Context() as c:
            profile.enable()

            # findings:
            #  - Path.is_absolute() much faster than os.path.isabs()
            #  - os.path.join(root_path_str, *p.parts) is much faster than c.root_path / p
            #  - pathlib is very slow

            # times for comparison:
            #   337 ms (originally)
            #   216 ms (with optimized managed_tree_path_of)
            #   90 ms (current - without pathlib)

            for i in range(10000):
                dlb.ex.worktree.read_filesystem_object_memo(
                    c.root_path / c.working_tree_path_of(p, existing=True, collapsable=False))

            profile.disable()

        dump_profile_stats(profile, self, 1)

    def test_decode_encoded_path(self):
        profile = cProfile.Profile()
        profile.enable()

        # findings:
        #
        #  - decode_encoded_path() is dominated by constructor of dlb.fs.Path
        #  - construction of dlb.fs.Path is faster by str than by components

        # times for comparison: 405 ms

        for i in range(100000):
            dlb.ex.rundb.decode_encoded_path('a/b2/c33/d42/')

        profile.disable()
        dump_profile_stats(profile, self, 2)

    def test_inform(self):
        profile = cProfile.Profile()

        dlb.di.set_threshold_level(dlb.di.WARNING)
        message = 'abc' * 20  # typical for dlb.di.Cluster(): one line, no control characters

        profile.enable()

        for i in range(10000):
            with dlb.di.Cluster(message):
                pass

        profile.disable()
        dump_profile_stats(profile, self, 3)

    def test_join_paths(self):
        profile = cProfile.Profile()
        profile.enable()

        r = dlb.fs.WindowsPath('a/b/c/')
        p = dlb.fs.WindowsPath('d/e')
        for i in range(10000):
            r / p

        profile.disable()
        dump_profile_stats(profile, self, 4)


class ImportantImportBenchmark(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_define_tool(self):

        profile = cProfile.Profile()
        profile.enable()

        class BTool(dlb.ex.Tool):
            PARAMETER = ()
            PARAMETER2 = 123

            input = dlb.ex.Tool.Input.RegularFile()
            output = dlb.ex.Tool.Output.RegularFile()

            def redo(self, result, context):
                pass

        # noinspection PyUnusedLocal
        class CTool(BTool):
            PARAMETER = (1, 2, 3)
            PARAMETER3 = ''

            output2 = dlb.ex.Tool.Output.RegularFile()

            def redo(self, result, context):
                pass

        profile.disable()
        dump_profile_stats(profile, self, 1)
