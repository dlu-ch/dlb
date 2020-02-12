# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path


def sanitize_module_search_path():
    sys.path = [os.path.abspath(p) for p in sys.path]


# make sure sys.path does not a relative path before you import a module inside
sanitize_module_search_path()

import os
import tempfile
import unittest


class DirectoryChanger:  # change directory temporarily
    def __init__(self, path, show_dir_change=False):
        self._path = path
        self._show_dir_change = show_dir_change

    def __enter__(self):
        self._original_path = os.getcwd()
        os.chdir(self._path)
        if self._show_dir_change:
            print(f'changed current working directory of process to {self._path!r}')

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self._original_path)
        if self._show_dir_change:
            print(f'changed current working directory of process back to {self._original_path!r}')


class TemporaryDirectoryTestCase(unittest.TestCase):  # change to temporary directory during test
    def __init__(self, *args, show_dir_change=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._show_dir_change = show_dir_change
        self._original_cwd = None
        self._temp_dir = None

    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.TemporaryDirectory()
        try:
            os.chdir(self._temp_dir.name)
            if self._show_dir_change:
                print(f'changed current working directory of process to {self._temp_dir.name!r}')
        except:
            self._temp_dir.cleanup()

    def tearDown(self):
        if self._temp_dir:
            try:
                os.chdir(self._original_cwd)
                if self._show_dir_change:
                    print(f'changed current working directory of process back to {self._original_cwd!r}')
            finally:
                self._temp_dir.cleanup()

