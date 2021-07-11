# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2021 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Manipulate Python module search paths in a portable way."""

# Usage example:
#
#   import dlb_contrib.python
#   build_directory = dlb.fs.Path('build/')
#   dlb_contrib.python.prepend_to_module_search_path(
#       build_directory / 'python/',
#       build_directory / 'out/gsrc/python/'
#   )
#   import my_specific_module  # found in 'build/python/my_specific_module.py'

__all__ = ['prepend_to_module_search_path']

import sys
import os.path

import dlb.fs

assert sys.version_info >= (3, 7)


def prepend_to_module_search_path(*paths: dlb.fs.PathLike):
    # Prepends the absolute (real) path equivalent to each path in *paths* to the current list of
    # module search paths *sys.path* and removes all existing occurrences.
    #
    # The resulting order in *sys.path* is the same as in *paths*.

    for path in reversed(paths):
        path = dlb.fs.Path(path)
        if not path.is_dir():
            raise ValueError(f'cannot prepend non-directory: {path.as_string()!r}')
        real_path = os.path.realpath(str(dlb.fs.Path(path).native))
        sys.path = [real_path] + [p for p in sys.path if p != real_path]
