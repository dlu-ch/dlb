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
from typing import TypeVar, Optional, Union
from . import path as path_


# path
P = TypeVar('P', bound=Union[path_.Path, pathlib.Path])

# pure path
PP = TypeVar('PP', bound=Union[path_.Path, pathlib.PurePath])


class PathNormalizationError(ValueError):
    def __init__(self, *args, oserror: Optional[OSError] = None):
        super().__init__(*args)
        self.oserror = oserror


@dataclasses.dataclass
class FilesystemStatSummary:
    mode: int
    size: int
    mtime_ns: int
    uid: int
    gid: int


@dataclasses.dataclass
class FilesystemObjectMemo:
    stat: Optional[FilesystemStatSummary] = None
    symlink_target: Optional[str] = None


class _KeepFirstRmTreeException:
    def __init__(self):
        self.first_exception = None

    def __call__(self, f, p: Exception, excinfo):
        _, value, _ = excinfo
        if self.first_exception is None and value is not None:
            self.first_exception = value


def remove_filesystem_object(abs_path: Union[str, pathlib.Path, path_.Path], *,
                             abs_empty_dir_path: Union[None, str, pathlib.Path, path_.Path] = None,
                             ignore_non_existing: bool = False):
    """
    Remove the filesystem objects with absolute path *abs_path*.

    If *abs_path* refers to an existing symbolic link to an existing target, the symbolic link is removed,
    not the target.

    If *abs_path* refers to an existing directory (empty or not empty) and *abs_temp_path* is not ``None``,
    the directory is first moved to *abs_empty_dir_path*.
    Then the moved directory with its content is removed; errors are silently ignored.
    
    *abs_temp_path* is not ``None``, is must denote an empty and writable directory on the same filesystem
    as *abs_path*. Use a temporary directory, if possible.    

    :raise ValueError:
        if *abs_path* is ``None`` or is not an absolute path,
        or if *abs_empty_dir_path* is ``None`` and is not an absolute path
    :raise FileNotFoundError:
        if *abs_path* does not exists and *ignore_non_existing* is ``True``
    :raise OSError:
        if an existing *abs_path* was not removed
    """

    if isinstance(abs_path, bytes):
        # prevent special treatment by byte paths
        raise TypeError("'abs_path' must be a str, pathlib.Path or dlb.fs.Path object, not bytes")

    if isinstance(abs_empty_dir_path, bytes):
        # prevent special treatment by byte paths
        raise TypeError("'abs_empty_dir_path' must be a str, pathlib.Path or dlb.fs.Path object, not bytes")

    if isinstance(abs_path, path_.Path):
        abs_path = abs_path.native.raw

    if not os.path.isabs(abs_path):  # does not raise OSError
        raise ValueError(f"not an absolute path: {str(abs_path)!r}")

    if abs_empty_dir_path is not None:
        if isinstance(abs_empty_dir_path, path_.Path):
            abs_empty_dir_path = abs_empty_dir_path.native.raw

        if not os.path.isabs(abs_empty_dir_path):  # does not raise OSError
            raise ValueError(f"not an absolute path: {str(abs_empty_dir_path)!r}")

    is_directory = False
    try:
        try:
            os.remove(abs_path)  # does remove symlink, not target
            # according to the Python 3.8 documentation, 'IsADirectoryError' is raised if 'abs_path' is a directory;
            # however, on Windows 10 PermissionError is raised instead
        except IsADirectoryError:
            is_directory = True
        except PermissionError:
            is_directory = os.path.isdir(abs_path)
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


def read_filesystem_object_memo(abs_path: Union[str, pathlib.Path, path_.Path]) -> FilesystemObjectMemo:
    """
    Returns the summary of the filesystem's meta-information for a filesystem object with absolute path *abs_path*
    as a ``FilesystemObjectMemo`` object.

    If ``memo.stat`` contains the following members from ``stat_result`` (with ``st_`` removed from their names,
    all integers):

      - ``mode``
      - ``size``
      - ``mtime_ns``
      - ``uid``
      - ``gid``

    If  *memo.stat.mode* indicates a symbolic link, *memo.symlink_target* is the path of its target as a string.
    Otherwise, *memo.symlink_target* is None.
    """
    if isinstance(abs_path, bytes):
        raise TypeError("'abs_path' must be a str or path, not bytes")  # prevent special treatment by byte paths

    if isinstance(abs_path, path_.Path):
        abs_path = abs_path.native.raw

    if not os.path.isabs(abs_path):  # does not raise OSError
        raise ValueError(f"not an absolute path: {str(abs_path)!r}")

    memo = FilesystemObjectMemo()

    sr = os.lstat(abs_path)
    memo.stat = FilesystemStatSummary(mode=sr.st_mode, size=sr.st_size, mtime_ns=sr.st_mtime_ns,
                                      uid=sr.st_uid, gid=sr.st_gid)

    if not stat.S_ISLNK(sr.st_mode):
        return memo

    memo.symlink_target = os.readlink(abs_path)  # a trailing '/' is preserved
    return memo


def _normalize_dotdot(path: PP, ref_dir_path: Union[None, str, os.PathLike]) -> PP:
    path_components = path.parts

    root = ()
    nonroot_components = path_components
    if path.is_absolute():
        root = nonroot_components[:1]
        nonroot_components = nonroot_components[1:]

    while True:
        try:
            i = nonroot_components.index('..')
        except ValueError:
            break

        if i == 0:
            path = path.as_string() if isinstance(path, path_.Path) else str(path)
            raise PathNormalizationError(f"is an upwards path: {path!r}")

        if ref_dir_path is not None:
            p = os.path.join(ref_dir_path, *root, *nonroot_components[:i])
            sr = os.lstat(p)
            if stat.S_ISLNK(sr.st_mode):
                msg = f"not a collapsable path, since this is a symbolic link: {p!r}"
                raise PathNormalizationError(msg) from None

        nonroot_components = nonroot_components[:i - 1] + nonroot_components[i + 1:]

    components = root + nonroot_components

    if components == path_components:
        return path

    if isinstance(path, path_.Path):
        return path.__class__(pathlib.PurePosixPath(*components), is_dir=path.is_dir())

    return path.__class__(*components)


def normalize_dotdot_collapsable(path: PP) -> PP:
    """
    Return an equivalent normal *path* with all :file:`..` components replaced, *assuming* that *path* is collapsable.
    The return value is of the same type as *path* and contains no :file:`..` components.

    Does not access the filesystem and does not raise :exc:`OSError`.

    :raise PathNormalizationError: if *path* is an upwards path
    :raise ValueError: if the resulting path is not representable with the type of *path*
    """
    if not isinstance(path, (path_.Path, pathlib.PurePath)):
        raise TypeError(f"'path' must be a dlb.fs.Path or pathlib.PurePath object")

    return _normalize_dotdot(path, None)


def normalize_dotdot(path: P, ref_dir_path: Union[str, os.PathLike, path_.Path] = None) -> P:
    """
    Return an equivalent normal *path* with all :file:`..` components replaced, if it is collapsable.

    *ref_dir_path* must be an absolute path as a :class:`pathlib.Path` or :class:`dlb.fs.Path`.
    It is then used as the reference directory for a relative *path*.

    The return value is of the same type as *path* and contains no :file:`..` components.

    Does not access the filesystem unless *path* contains a :file:`..` component.

    Does not raise :exc:`OSError`. If an filesystem access fails, a :exc:`PathNormalizationError` is raised with
    the attribute `oserror` set to a :exc:`OSError` instance.

    :raise PathNormalizationError: if *path* is an upwards path or not collapsable or a filesystem access failed
    :raise ValueError: if the resulting path is not representable with the type of *path*
    """
    if not isinstance(path, (path_.Path, pathlib.Path)):
        raise TypeError(f"'path' must be a dlb.fs.Path or pathlib.Path object")

    if isinstance(ref_dir_path, path_.Path):
        ref_dir_path = ref_dir_path.native.raw
    if isinstance(ref_dir_path, os.PathLike):  # note: str is not os.PathLike
        ref_dir_path = os.fspath(ref_dir_path)
    if not isinstance(ref_dir_path, str):
        raise TypeError(f"'ref_dir_path' must be a str or a dlb.fs.Path or os.PathLike object returning str")

    if not os.path.isabs(ref_dir_path):
        raise ValueError("'ref_dir_path' must be absolute")

    try:
        return _normalize_dotdot(path, ref_dir_path)
    except OSError as e:
        raise PathNormalizationError(oserror=e) from None
