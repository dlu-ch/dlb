# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.ex
import dlb_contrib.partition
import os
import unittest


class ByWorkingTreePathTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_empty_for_empty(self):
        with dlb.ex.Context():
            self.assertEqual([], dlb_contrib.partition.by_working_tree_path([], number_of_groups=3))

    def test_all_in_same_group_for_nonpositive(self):
        paths = ['a', dlb.fs.Path('b')]
        with dlb.ex.Context():
            self.assertEqual([paths], dlb_contrib.partition.by_working_tree_path(paths, number_of_groups=0))

    def test_similar_in_same_group(self):
        paths = ['a', dlb.fs.Path('a/'), 'a', './a', 'a////', ('', 'a')]
        groups = [
            [dlb.fs.Path('a/'), 'a////'],
            ['a', 'a', './a', ('', 'a')]
        ]
        with dlb.ex.Context():
            self.assertEqual(groups, dlb_contrib.partition.by_working_tree_path(paths, number_of_groups=2))

    def test_distributes_well_for_small_number(self):
        paths = ['a', 'b', 'c', 'd', 'e', 'f', 'g']

        with dlb.ex.Context():
            groups = dlb_contrib.partition.by_working_tree_path(paths, number_of_groups=2)
        self.assertEqual(len(paths), sum(len(g) for g in groups))

        group_indices = []
        for p in paths:
            for i, g in enumerate(groups):
                if p in g:
                    group_indices.append(i)
                    break
        self.assertEqual(len(paths), len(group_indices))
        starts_of_run = [j for j, i in enumerate(group_indices[:-1]) if i == group_indices[j + 1]]

        self.assertLessEqual(len(starts_of_run), 1, starts_of_run)


class SplitLongerTest(unittest.TestCase):

    def test_empty_for_empty(self):
        self.assertEqual([], dlb_contrib.partition.split_longer([], max_length=3))

    def test_splits_longer(self):
        self.assertEqual([[1, 2], [3, 4, 5], [6, 7], [8]],
                         dlb_contrib.partition.split_longer([[1, 2], [3, 4, 5, 6, 7], [8]], max_length=3))
