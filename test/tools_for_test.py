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
import pathlib
import tempfile
import shutil
from typing import Union
import unittest


class DirectoryChanger:  # change directory temporarily
    def __init__(self, path: Union[str, os.PathLike, pathlib.Path], show_dir_change=False):
        self._path = pathlib.Path(path)
        self._show_dir_change = show_dir_change

    def __enter__(self):
        self._original_path = pathlib.Path.cwd()
        os.chdir(os.fspath(self._path))
        if self._show_dir_change:
            print(f'changed current working directory of process to {str(self._path)!r}')

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(os.fspath(self._original_path))
        if self._show_dir_change:
            print(f'changed current working directory of process back to {str(self._original_path)!r}')


class TemporaryDirectoryTestCase(unittest.TestCase):  # change to temporary directory during test
    def __init__(self, *args, show_dir_change=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._show_dir_change = show_dir_change
        self._original_cwd = None
        self._temp_dir_path = None

    def setUp(self):
        self._original_cwd = os.getcwd()
        self._temp_dir_path = os.path.abspath(tempfile.mkdtemp())
        try:
            os.chdir(self._temp_dir_path)
            if self._show_dir_change:
                print(f'changed current working directory of process to {self._temp_dir_path!r}')
        except OSError:
            shutil.rmtree(self._temp_dir_path, ignore_errors=True)
            raise

    def tearDown(self):
        if self._temp_dir_path:
            try:
                os.chdir(self._original_cwd)
                if self._show_dir_change:
                    print(f'changed current working directory of process back to {self._original_cwd!r}')
            finally:
                shutil.rmtree(self._temp_dir_path, ignore_errors=True)


class TemporaryDirectoryWithChmodTestCase(TemporaryDirectoryTestCase):

    def setUp(self):
        super().setUp()

        probe_dir = pathlib.Path('chmodprobe')
        probe_dir.mkdir()

        probe_dir.chmod(0o000)
        probe_file = probe_dir / 'x'

        try:
            try:
                with probe_file.open('xb'):
                    pass
            except OSError:
                pass
            else:
                self.assertNotEqual(os.name, 'posix', "on any POSIX system permission should be denied")
                raise unittest.SkipTest
        finally:
            probe_dir.chmod(0o700)
            if probe_file.exists():
                probe_file.unlink()
            probe_dir.rmdir()


class TemporaryWorkingDirectoryTestCase(TemporaryDirectoryTestCase):

    def setUp(self):
        super().setUp()
        os.mkdir('.dlbroot')