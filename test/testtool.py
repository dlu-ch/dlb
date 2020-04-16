# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
import os
import io
import pathlib
import tempfile
import shutil
import unittest
from typing import Union

# PyCharm detects unittests in a source file if one of the following conditions is true:
#
#  - The source file defines a subclass of unittest.TestCase.
#  - The source file defines a subclass of class *C* which is a subclass of unittest.TestCase, and
#    the definition of *C* is "found" by PyCharm (the source file of the defining module is in one of the
#    Source Folder defined in the project settings).
#
# Therefore, the first unitest in each test source file should be a direct subclass of unittest.TestCase.


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
        # noinspection PyTypeChecker
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
        import dlb.di
        super().setUp()
        os.mkdir('.dlbroot')
        dlb.di.set_threshold_level(dlb.di.INFO)
        dlb.di.set_output_file(sys.stderr)


class CommandlineToolTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._path = None
        self._argv = None
        self._stdout = None
        self._stderr = None

    def setUp(self):
        super().setUp()
        self._path = list(sys.path)
        self._argv = list(sys.argv)
        sys.argv = [sys.argv[0]]
        self._stdout = sys.stdout
        sys.stdout = io.StringIO()
        self._stderr = sys.stderr
        sys.stderr = io.StringIO()

    def tearDown(self):
        sys.path = self._path
        sys.argv = self._argv
        sys.stderr.close()
        sys.stderr = self._stderr
        sys.stdout.close()
        sys.stdout = self._stdout
