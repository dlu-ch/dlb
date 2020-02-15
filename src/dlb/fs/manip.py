# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Filesystem manipulations.
This is an implementation detail - do not import it unless you know what you are doing."""

import os
import stat
import pathlib
import shutil
import dataclasses
import typing
from . import path


class _KeepFirstRmTreeException:
    def __init__(self):
        self.first_exception = None

    def __call__(self, f, p: Exception, excinfo):
        _, value, _ = excinfo
        if self.first_exception is None and value is not None:
            self.first_exception = value


def remove_filesystem_object(abs_path: typing.Union[str, pathlib.Path, path.Path], *,
                             abs_empty_dir_path: typing.Optional[typing.Union[str, pathlib.Path, path.Path]] = None,
                             ignore_non_existing: bool = False):
    """
    Remove the filesystem objects with absolute path `abs_path`.

    If `abs_path` refers to an existing symbolic link to an existing target, the symbolic link is removed,
    not the target.

    If `abs_path` refers to an existing directory (empty or not empty) and `abs_temp_path` is not `None`, the directory
    is first moved to `abs_empty_dir_path` (which must be an empty, writable directory on the same filesystem as
    `abs_path`, usually a temporary directory).
    Then the moved directory with its content is removed; errors are silently ignored.

    :raise ValueError:
        if `abs_path` is `None` or is not an absolute path,
        or if `abs_empty_dir_path` is `None` and is not an absolute path
    :raise FileNotFoundError:
        if `abs_path` does not exists and `ignore_non_existing` is `True`
    :raise OSError:
        if an existing `abs_path` was not removed
    """

    if isinstance(abs_path, bytes):
        # prevent special treatment by byte paths  ???
        raise TypeError("'abs_path' must be a str or path, not bytes")

    if isinstance(abs_empty_dir_path, bytes):
        # prevent special treatment by byte paths
        raise TypeError("'abs_empty_dir_path' must be a str or path, not bytes")

    if isinstance(abs_path, path.Path):
        abs_path = abs_path.native.raw

    if not os.path.isabs(abs_path):  # does not raise OSError
        raise ValueError(f"not an absolute path: {str(abs_path)!r}")

    if abs_empty_dir_path is not None:
        if isinstance(abs_empty_dir_path, path.Path):
            abs_empty_dir_path = abs_empty_dir_path.native.raw

        if not os.path.isabs(abs_empty_dir_path):  # does not raise OSError
            raise ValueError(f"not an absolute path: {str(abs_empty_dir_path)!r}")

    is_directory = False
    try:
        try:
            os.remove(abs_path)  # does remove symlink, not target
        except IsADirectoryError:
            is_directory = True
    except FileNotFoundError:
        if not ignore_non_existing:
            raise

    if not is_directory:
        return

    # was a directory on last remove attempt
    try:
        if abs_empty_dir_path is None:
            lke = _KeepFirstRmTreeException()
            shutil.rmtree(abs_path, onerror=lke)  # remove in place (as much as possible)
            if lke.first_exception is not None:
                raise lke.first_exception
        else:
            abs_temp_dir_path = os.path.join(abs_empty_dir_path, 't')  # non-existing directory
            os.rename(abs_path, abs_temp_dir_path)  # POSIX: atomic on same filesystem
            shutil.rmtree(abs_temp_dir_path, ignore_errors=True)  # remove as much as possible
    except FileNotFoundError:
        if not ignore_non_existing:
            raise


@dataclasses.dataclass
class FilesystemStatSummary:
    mode: int
    size: int
    mtime_ns: int
    uid: int
    gid: int


@dataclasses.dataclass
class FilesystemObjectMemo:
    stat: typing.Optional[FilesystemStatSummary] = None
    symlink_target: typing.Optional[str] = None


def read_filesystem_object_memo(abs_path: typing.Union[str, pathlib.Path, path.Path]) -> FilesystemObjectMemo:
    """
    Return a summary of the filesystem's meta-information on a filesystem object with absolute path `abs_path`.

    Its `stat` attribute contains the following members from `stat_result` as integers
    (with `st_` removed from their names):

      - `mode`
      - `size`
      - `mtime_ns`
      - `uid`
      - `gid`

    If `r.stat.mode` of the returned object `r` indicates a symbolic link, `r.symlink_target` is the path of its target
    as a str. Otherwise, `r.symlink_target` is None.
    """
    if isinstance(abs_path, bytes):
        raise TypeError("'abs_path' must be a str or path, not bytes")  # prevent special treatment by byte paths

    if isinstance(abs_path, path.Path):
        abs_path = abs_path.native.raw

    if not os.path.isabs(abs_path):  # does not raise OSError
        raise ValueError(f"not an absolute path: {str(abs_path)!r}")

    memo = FilesystemObjectMemo()
    try:
        sr = os.lstat(abs_path)
        memo.stat = FilesystemStatSummary(mode=sr.st_mode, size=sr.st_size, mtime_ns=sr.st_mtime_ns,
                                          uid=sr.st_uid, gid=sr.st_gid)
    except FileNotFoundError:
        return memo

    if not stat.S_ISLNK(sr.st_mode):
        return memo

    memo.symlink_target = os.readlink(abs_path)  # a trailing '/' is preserved
    return memo
