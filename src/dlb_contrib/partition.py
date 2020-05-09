# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Partition filesystem objects in the managed tree."""

# Usage example:
#
#   import dlb.fs
#   import dlb_contrib.partition
#
#   paths = dlb.fs.Path(...).list(...)
#   path_groups = dlb_contrib.partition.by_working_tree_path(paths, number_of_groups=1000)
#   # path_groups now contains (at most 1000) non-empty lists of elements of *paths*
#
#   path_groups = dlb_contrib.partition.split_longer(path_groups, max_length=5)
#   # path_groups now contains (non-empty) lists with at most 5 members

__all__ = ['by_working_tree_path', 'split_longer']

import sys
import zlib
from typing import Any, Iterable, List, Sequence

import dlb.fs
import dlb.ex

assert sys.version_info >= (3, 7)


def by_working_tree_path(paths: Sequence[dlb.fs.PathLike], *, number_of_groups: int, collapsable=False) \
        -> List[List[dlb.fs.PathLike]]:

    # Partition *paths* into *number_of_groups* groups based on their working tree path in a stable and portable way
    # (the result is the same for the same paths on all supported platforms, Python versions and dlb runs).
    #
    # If *paths* contains multiple paths with the same working tree path, all of them are placed in the same group.
    # Otherwise, the length of the groups is "similar*.
    # More precisely:
    # For *m* > 0 elements in *paths* and *number_of_groups* >= 1, all with different and uniformely distributed hashes
    # of their working tree paths, the expected value of the length of each group is *m* / *number_of_groups*.
    #
    # If *collapsable* is True, all paths in *paths* are assumed to be collapsable (only relevant if at least one of
    # them contains a '..' component).
    #
    # Returns a list of at most *number_of_groups* non-empty lists of elements of *paths* that together contain all
    # elements of *path* if *number_of_groups* > 0 and [] otherwise.

    number_of_groups = int(number_of_groups)
    collapsable = bool(collapsable)
    context = dlb.ex.Context.active

    working_tree_paths = [
        context.working_tree_path_of(p, allow_temporary=True, existing=True, collapsable=collapsable)
        for p in paths
    ]

    if not paths:
        return []

    if number_of_groups <= 1:
        return [list(paths)]

    groups = [[] for _ in range(number_of_groups)]
    for i in range(len(paths)):
        b = working_tree_paths[i].as_string().encode()
        h = zlib.crc32(b, zlib.crc32(b))  # concatenation reduces runs for short *b* in small *number_of_groups*
        groups[h % number_of_groups].append(paths[i])

    return [g for g in groups if g]


def split_longer(sequence: Iterable[Sequence[Any]], *, max_length: int) -> List[List[Any]]:
    # Return a list of all members of *sequence* as lists, split into list of at most *max_length* members if longer.
    # Order is preserved.
    #
    # Examples:
    #
    #   split_longer([], max_length=3)                              # []
    #   split_longer([[1, 2], [3, 4, 5, 6, 7], [8]], max_length=3)  # [[1, 2], [3, 4, 5], [6, 7], [8]]

    max_length = max(1, int(max_length))
    list_of_smaller = []
    for seq in sequence:
        seq = list(seq)
        while seq:
            list_of_smaller.append(seq[:max_length])
            seq = seq[max_length:]
    return list_of_smaller
