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
from . import path as path_


# path
P = typing.TypeVar('P', bound=typing.Union[path_.Path, pathlib.Path])

# pure path
PP = typing.TypeVar('PP', bound=typing.Union[path_.Path, pathlib.PurePath])


class PathNormalizationError(ValueError):
    pass


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


class _KeepFirstRmTreeException:
    def __init__(self):
        self.first_exception = None

    def __call__(self, f, p: Exception, excinfo):
        _, value, _ = excinfo
        if self.first_exception is None and value is not None:
            self.first_exception = value


def remove_filesystem_object(abs_path: typing.Union[str, pathlib.Path, path_.Path], *,
                             abs_empty_dir_path: typing.Union[None, str, pathlib.Path, path_.Path] = None,
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


def read_filesystem_object_memo(abs_path: typing.Union[str, pathlib.Path, path_.Path]) \
        -> typing.Tuple[FilesystemObjectMemo, typing.Optional[os.stat_result]]:
    """
    Return a tuple `(memo, sr)`, where *memo* is the summary of the filesystem's meta-information for a
    filesystem object with absolute path *abs_path*, and *sr* is the corresponding ``os.stat_result`` object.
    *memo* is a ``FilesystemObjectMemo`` object.

    If *abs_path* exists, *sr* is its ``stat_result`` and ``memo.stat`` contains the following members from *sr*
    (with ``st_`` removed from their names, all integers):

      - ``mode``
      - ``size``
      - ``mtime_ns``
      - ``uid``
      - ``gid``

    If *abs_path* does not exists, *sr* and *memo.stat* are ``Ǹone``.

    If *memo.stat* is not ``None`` and *memo.stat.mode* indicates a symbolic link, *memo.symlink_target* is the path of
    its target as a string. Otherwise, *memo.symlink_target* is None.

    Does not raise ``FileNotFoundError``.
    """
    if isinstance(abs_path, bytes):
        raise TypeError("'abs_path' must be a str or path, not bytes")  # prevent special treatment by byte paths

    if isinstance(abs_path, path_.Path):
        abs_path = abs_path.native.raw

    if not os.path.isabs(abs_path):  # does not raise OSError
        raise ValueError(f"not an absolute path: {str(abs_path)!r}")

    memo = FilesystemObjectMemo()
    try:
        sr = os.lstat(abs_path)
        memo.stat = FilesystemStatSummary(mode=sr.st_mode, size=sr.st_size, mtime_ns=sr.st_mtime_ns,
                                          uid=sr.st_uid, gid=sr.st_gid)
    except FileNotFoundError:
        return memo, None

    if not stat.S_ISLNK(sr.st_mode):
        return memo, sr

    memo.symlink_target = os.readlink(abs_path)  # a trailing '/' is preserved
    return memo, sr


def _normalize_dotdot(path: PP, ref_dir_path: typing.Optional[str]) -> PP:

    # TODO accept str (as a native path) for performance reasons

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
            raise PathNormalizationError(f"is an upwards path: {path!r}")
        if ref_dir_path:
            p = os.path.join(ref_dir_path, *root, *nonroot_components[:i])
            try:
                sr = os.lstat(p)
                if stat.S_ISLNK(sr.st_mode):
                    msg = f"not a collapsable path, since this is a symbolic link: {p!r}"
                    raise PathNormalizationError(msg) from None
            except OSError as e:
                raise PathNormalizationError(f"check failed with {e.__class__.__name__}: {p!r}") from None
        nonroot_components = nonroot_components[:i - 1] + nonroot_components[i + 1:]

    components = root + nonroot_components

    if components == path_components:
        return path

    if isinstance(path, path_.Path):
        return path.__class__(pathlib.PurePosixPath(*components), is_dir=path.is_dir())

    return path.__class__(*components)


def normalize_dotdot_pure(path: PP) -> PP:
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


def normalize_dotdot(path: P, ref_dir_path: typing.Union[path_.Path, pathlib.Path] = None) -> P:
    """
    Return an equivalent normal *path* with all :file:`..` components replaced, if it is collapsable.

    *ref_dir_path* must be an absolute path as a :class:`pathlib.Path` or :class:`dlb.fs.Path`.
    It is then used as the reference directory for a relative *path*.

    The return value is of the same type as *path* and contains no :file:`..` components.

    Does not access the filesystem unless *path* contains a :file:`..` component.
    Does not raise :exc:`OSError`.

    :raise PathNormalizationError: if *path* is an upwards path or not collapsable
    :raise ValueError: if the resulting path is not representable with the type of *path*
    """
    if not isinstance(path, (path_.Path, pathlib.Path)):
        raise TypeError(f"'path' must be a dlb.fs.Path or pathlib.Path object")

    if isinstance(ref_dir_path, path_.Path):
        ref_dir_path = ref_dir_path.native.raw
    elif not isinstance(ref_dir_path, pathlib.Path):
        raise TypeError(f"'ref_dir_path' must be a dlb.fs.Path or pathlib.Path object")

    if not ref_dir_path.is_absolute():
        raise ValueError("'ref_dir_path' must be absolute")

    ref_dir_path = str(ref_dir_path)  # TODO remove

    return _normalize_dotdot(path, ref_dir_path)


def normalize_dotdot_with_memo_relative_to(path: P, ref_dir_real_native_path: str) \
        -> typing.Tuple[P, FilesystemObjectMemo, os.stat_result]:
    """
    Return a tuple ``(normal_path, sr)``, where *normal_path* is a normal path without symbolic links, pointing to the
    same existing filesystem object as *path* and relative to *ref_dir_real_native_path*, and *sr* is its
    ``os.stat_result`` object.
    *normal_path* is of the same type as *path* and contains no :file:`..` components.

    (This is like a more strict and "relative version" of :meth:`:python:os.path.realpath()`).

    *ref_dir_real_native_path* must be equivalent to the return value of :meth:`:python:os.path.realpath()`.

    Does not raise :exc:`OSError`.

    :raise PathNormalizationError:
        if the result would be an upwards path or *path* is not "inside" *ref_dir_real_native_path*
    :raise ValueError:
        if the *ref_dir_real_native_path* is an relative path or
        if the resulting path is not representable with the type of *path*
    """

    if not isinstance(path, (path_.Path, pathlib.Path)):
        raise TypeError(f"'path' must be a dlb.fs.Path or pathlib.Path object")

    if not isinstance(ref_dir_real_native_path, str):
        raise TypeError("'ref_dir_real_native_path' must be a str")

    if not os.path.isabs(ref_dir_real_native_path):
        raise ValueError("'ref_dir_real_native_path' must be absolute")

    pathlib_or_str_path: pathlib.PurePath = path.pure_posix if isinstance(path, path_.Path) else path
    if not pathlib_or_str_path.is_absolute():
        was_absolute = False
        # noinspection PyTypeChecker
        pathlib_or_str_path: str = os.path.join(ref_dir_real_native_path, pathlib_or_str_path)
    else:
        was_absolute = True

    try:
        memo_before, sr_before = read_filesystem_object_memo(pathlib_or_str_path)  # access the filesystem
        if sr_before is None:
            raise PathNormalizationError(f"does not exist: {str(pathlib_or_str_path)!r}") from None

        # TODO replace os.path.realpath() - only resolve prefix paths that differ
        real_abs_path = os.path.realpath(pathlib_or_str_path)  # access the filesystem (for each prefix path)

        memo_after, sr_after = read_filesystem_object_memo(pathlib_or_str_path)  # access the filesystem
        if sr_after is None or not os.path.samestat(sr_before, sr_after):
            raise FileNotFoundError

        i = len(ref_dir_real_native_path)
        if not (real_abs_path.startswith(ref_dir_real_native_path) and real_abs_path[i:i + 1] in ('', os.path.sep)):
            if was_absolute:
                raise PathNormalizationError(f"'path' not in reference directory, check exact letter case: {path!r}")
            raise PathNormalizationError(f"'path' not in reference directory: {path!r}")

        real_rel_path = real_abs_path[i + 1:]
        if not real_rel_path:
            real_rel_path = '.'

    except OSError as e:
        raise PathNormalizationError(f"check failed with {e.__class__.__name__}: {pathlib_or_str_path!r}") from None

    return path.__class__(real_rel_path), memo_after, sr_after
