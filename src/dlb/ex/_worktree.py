# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Filesystem manipulations in the working tree.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = []

import string
import os
import stat
from typing import Optional, Tuple, Type, Union

from .. import ut
from .. import fs
from . import _error
from . import _rundb


# a directory containing a directory with this name is considered a working tree of dlb
MANAGEMENTTREE_DIR_NAME = '.dlbroot'

# a directory containing a directory with this name is considered a working tree of dlb
MTIME_PROBE_FILE_NAME = 'o'  # see G-F1
assert MTIME_PROBE_FILE_NAME.upper() != MTIME_PROBE_FILE_NAME

LOCK_DIRNAME = 'lock'  # see G-F1
TEMPORARY_DIR_NAME = 't'  # see G-F1
RUNDB_FILE_NAME_TEMPLATE = 'runs-{}.sqlite'  # see G-F1


class _KeepFirstRmTreeException:
    def __init__(self):
        self.first_exception = None

    def __call__(self, f, p: Exception, excinfo):
        _, value, _ = excinfo
        if self.first_exception is None and value is not None:
            self.first_exception = value


class UniquePathProvider:
    FIRST_CHARACTERS = string.ascii_lowercase
    CHARACTERS = FIRST_CHARACTERS + string.digits

    def __init__(self, root_path: fs.PathLike):
        self._root_path = fs.Path(root_path)
        self._i = 0

    @property
    def root_path(self):
        return self._root_path

    def generate(self, *, suffix: str = '', is_dir: bool = False) -> fs.Path:
        # Return a path unique to this object by appending a unique path component to *root_path*.
        #
        # The unique path component starts with a lower-case letter and ends with suffix.
        # It contains only lower-case letters and decimal digits between its first characters and the suffix.
        # If *suffix* is not empty, is must start with a character from strings.punctuation and must not contain '/'.
        #
        # After *n* successful calls of this method since construction, the number *m* of characters in the
        # last path component (without suffix) is
        #
        #    m = math.ceil((math.log2(35 * n / 26 + 1) / math.log2(36))).
        #
        # For n = 2**64, m is 13.
        # With an *suffix* that is a valid dlb.fs.PortablePosixPath of at most two characters, the unique path component
        # is a valid dlb.fs.PortablePosixPath for the first 3_519_940_422_753_201_122 ~= 1.5 * 2**61 calls.

        suffix = str(suffix)
        if suffix:
            if suffix[0] not in string.punctuation:
                raise ValueError(f"non-empty 'suffix' must start with character from "
                                 f"strings.punctuation, not {suffix[0]!r}")
            if '/' in suffix:
                raise ValueError(f"'suffix' must not contain '/': {suffix!r}")

        # assume a case-insensitive filesystem
        i = self._i
        i, d = divmod(i, len(self.FIRST_CHARACTERS))
        n = self.FIRST_CHARACTERS[d]
        while i > 0:
            i, d = divmod(i - 1, len(self.CHARACTERS))
            n += self.CHARACTERS[d]

        n += suffix
        if is_dir:
            n += '/'

        p = self._root_path / n

        self._i += 1
        return p


def remove_filesystem_object(abs_path: Union[str, fs.Path], *,
                             abs_empty_dir_path: Union[None, str, fs.Path] = None,
                             ignore_non_existent: bool = False):
    # Removes the filesystem objects with absolute path *abs_path*.
    #
    # If *abs_path* refers to an existing symbolic link to an existing target, the symbolic link is removed,
    # not the target.
    #
    # If *abs_path* refers to an existing directory (empty or not empty) and *abs_temp_path* is not ``None``,
    # the directory is first moved to *abs_empty_dir_path*.
    # Then the moved directory with its content is removed; errors are silently ignored.
    #
    # *abs_temp_path* is not ``None``, is must denote an empty and writable directory on the same filesystem
    # as *abs_path*. Use a temporary directory, if possible.

    if isinstance(abs_path, fs.Path):
        abs_path = str(abs_path.native)
    else:
        if isinstance(abs_path, bytes):
            # prevent special treatment by byte paths
            raise TypeError("'abs_path' must be a str or dlb.fs.Path object, not bytes")
        abs_path = os.fspath(abs_path)

    if not os.path.isabs(abs_path):  # does not raise OSError
        raise ValueError(f"not an absolute path: {str(abs_path)!r}")

    if abs_empty_dir_path is not None:
        if isinstance(abs_empty_dir_path, bytes):
            # prevent special treatment by byte paths
            raise TypeError("'abs_empty_dir_path' must be a str or dlb.fs.Path object, not bytes")

        if isinstance(abs_empty_dir_path, fs.Path):
            abs_empty_dir_path = str(abs_empty_dir_path.native)
        else:
            abs_empty_dir_path = os.fspath(abs_empty_dir_path)

        if not os.path.isabs(abs_empty_dir_path):  # does not raise OSError
            raise ValueError(f"not an absolute path: {str(abs_empty_dir_path)!r}")

    try:
        os.remove(abs_path)  # does remove symlink, not target
        return
        # according to the Python 3.8 documentation, 'IsADirectoryError' is raised if 'abs_path' is a directory;
        # however, on Windows 10 PermissionError is raised instead
    except IsADirectoryError:
        pass
    except PermissionError:
        if not os.path.isdir(abs_path):
            raise
    except FileNotFoundError:
        if not ignore_non_existent:
            raise
        return

    # was an existing directory at last remove attempt

    try:
        os.rmdir(abs_path)
        return
    except FileNotFoundError:
        return
    except OSError:
        pass

    # was an existing non-empty directory at last remove attempt

    import shutil
    try:
        if abs_empty_dir_path is None:
            lke = _KeepFirstRmTreeException()
            shutil.rmtree(abs_path, onerror=lke)  # remove in place (as much as possible)
            if lke.first_exception is not None:
                raise lke.first_exception
        else:
            abs_temp_dir_path = os.path.sep.join((abs_empty_dir_path, 't'))  # non-existent directory
            os.rename(abs_path, abs_temp_dir_path)  # POSIX: atomic on same filesystem
            shutil.rmtree(abs_temp_dir_path, ignore_errors=True)  # remove as much as possible
    except FileNotFoundError:
        if not ignore_non_existent:
            raise


class Temporary:
    def __init__(self, *, path_provider: UniquePathProvider, suffix: str = '', is_dir: bool = False):
        if not path_provider.root_path.is_absolute():
            raise ValueError("'root_path' of 'path_provider' must be absolute")
        self._path = path_provider.generate(suffix=suffix, is_dir=is_dir)
        self._temporary_path_provider = path_provider
        self._did_create = False

    @property
    def path(self) -> fs.Path:
        return self._path

    def __enter__(self) -> fs.Path:
        # create an empty directory or file, raise an FileExistsError if it exists
        p = self._path.native
        if self._path.is_dir():
            os.mkdir(p, mode=0o733)
        else:
            os.close(os.open(p, flags=os.O_CREAT | os.O_EXCL, mode=0o622))
        self._did_create = True
        return self._path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._did_create:
            remove_filesystem_object(self._path.native, ignore_non_existent=True)


def read_filesystem_object_memo(abs_path: Union[str, fs.Path]) -> _rundb.FilesystemObjectMemo:
    # Returns the summary of the filesystem's meta-information for a filesystem object with absolute path *abs_path*
    # as a ``FilesystemObjectMemo`` object.
    #
    # If ``memo.stat`` contains the following members from ``stat_result`` (with ``st_`` removed from their names,
    # all integers):
    #
    #   - ``mode``
    #   - ``size``
    #   - ``mtime_ns``
    #   - ``uid``
    #   - ``gid``
    #
    # If  *memo.stat.mode* indicates a symbolic link, *memo.symlink_target* is the path of its target as a string.
    # Otherwise, *memo.symlink_target* is None.

    # must be fast

    if isinstance(abs_path, fs.Path):
        is_abs = abs_path.is_absolute()
        abs_path = str(abs_path.native)
    else:
        if isinstance(abs_path, bytes):
            raise TypeError("'abs_path' must be a str or path, not bytes")  # prevent special treatment by byte paths
        abs_path = os.fspath(abs_path)
        is_abs = os.path.isabs(abs_path)  # does not raise OSError

    if not is_abs:
        raise ValueError(f"not an absolute path: {str(abs_path)!r}")

    sr = os.lstat(abs_path)

    memo = _rundb.FilesystemObjectMemo()
    memo.stat = _rundb.FilesystemStatSummary(mode=sr.st_mode, size=sr.st_size, mtime_ns=sr.st_mtime_ns,
                                             uid=sr.st_uid, gid=sr.st_gid)

    if not stat.S_ISLNK(sr.st_mode):
        return memo

    memo.symlink_target = os.readlink(abs_path)  # a trailing '/' is preserved
    return memo


def normalize_dotdot_native_components(components: Tuple[str, ...], *, ref_dir_path: Optional[str] = None) \
        -> Tuple[str, ...]:
    # Return the components a path equivalent to the relative path with components *components* with all
    # :file:`..` components replaced, if it is collapsable.
    #
    # *components* must consist only of elements of p.native.components[1:] for a dlb.fs.Path object *p*.
    #
    # If *ref_dir_path* is not ``None``, it must be an absolute path as a str.
    # It is then used as the reference directory for a relative *path*.
    #
    # The return value contains no :file:`..` components.
    #
    # Does not access the filesystem unless *components* contains a :file:`..` componen and *ref_dir_path* is
    # not ``None``.
    #
    # Does not raise :exc:`OSError`. If an filesystem access fails, a :exc:`PathNormalizationError` is raised with
    # the attribute `oserror` set to a :exc:`OSError` instance.
    #
    # :raise PathNormalizationError: if *path* is an upwards path or not collapsable or a filesystem access failed
    # :raise ValueError: if the resulting path is not representable with the type of *path*

    # must be fast

    normalized_components = tuple(str(c) for c in components)
    if ref_dir_path is not None:
        if not isinstance(ref_dir_path, str):
            raise TypeError("'ref_dir_path' must be a str")
        if not os.path.isabs(ref_dir_path):
            raise ValueError("'ref_dir_path' must be None or absolute")

    try:
        while True:
            try:
                i = normalized_components.index('..')
            except ValueError:
                break

            if i == 0:
                path = fs.Path(('',) + components)
                raise _error.WorkingTreePathError(f"is an upwards path: {path.as_string()!r}")

            if ref_dir_path is not None:
                p = os.path.sep.join((ref_dir_path,) + normalized_components[:i])
                sr = os.lstat(p)
                if stat.S_ISLNK(sr.st_mode):
                    msg = f"not a collapsable path, since this is a symbolic link: {p!r}"
                    raise _error.WorkingTreePathError(msg) from None

            normalized_components = normalized_components[:i - 1] + normalized_components[i + 1:]
    except OSError as e:
        raise _error.WorkingTreePathError(oserror=e) from None

    return normalized_components


def get_checked_root_path_from_cwd(cwd: str, path_cls: Type[fs.Path]):
    try:
        root_path = path_cls(path_cls.Native(cwd), is_dir=True)
    except (ValueError, OSError) as e:
        msg = (  # assume that ut.exception_to_string(e) contains the working_tree_path
            f'current directory violates imposed path restrictions\n'
            f'  | reason: {ut.exception_to_line(e)}\n'
            f'  | move the working directory or choose a less restrictive path class for the root context'
        )
        raise ValueError(msg) from None

    # from pathlib.py of Python 3.7.3:
    # "NOTE: according to POSIX, getcwd() cannot contain path components which are symlinks."

    root_path_str = str(root_path.native)

    try:
        # may raise FileNotFoundError, RuntimeError
        real_root_path = root_path.native.raw.resolve(strict=True)
        if real_root_path != root_path.native.raw:
            raise ValueError
    except (ValueError, OSError, RuntimeError):
        msg = (
            "supposedly equivalent forms of current directory's path point to different filesystem objects\n"
            "  | reason: unresolved symbolic links, dlb bug, Python bug or a moved directory\n"
            "  | try again?"
        )
        raise _error.NoWorkingTreeError(msg) from None

    msg = (
        f'current directory is no working tree: {root_path.as_string()!r}\n'
        f'  | reason: does not contain a directory {MANAGEMENTTREE_DIR_NAME!r} '
        f'(that is not a symbolic link)'
    )
    try:
        mode = os.lstat(os.path.join(root_path_str, MANAGEMENTTREE_DIR_NAME)).st_mode
    except Exception:
        raise _error.NoWorkingTreeError(msg) from None
    if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
        raise _error.NoWorkingTreeError(msg) from None

    return root_path


def lock_working_tree(root_path: fs.Path):
    lock_dir_path = os.path.join(str(root_path.native), MANAGEMENTTREE_DIR_NAME, LOCK_DIRNAME)
    try:
        try:
            mode = os.lstat(lock_dir_path).st_mode
            if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
                remove_filesystem_object(lock_dir_path)
        except FileNotFoundError:
            pass
        os.mkdir(lock_dir_path)
    except OSError as e:
        msg = (
            f'cannot acquire lock for exclusive access to working tree {root_path.as_string()!r}\n'
            f'  | reason: {ut.exception_to_line(e)}\n'
            f'  | to break the lock (if you are sure no other dlb process is running): '
            f'remove {lock_dir_path!r}'
        )
        raise _error.ManagementTreeError(msg) from None


def unlock_working_tree(root_path: fs.Path):
    lock_dir_path = os.path.join(str(root_path.native), MANAGEMENTTREE_DIR_NAME, LOCK_DIRNAME)
    os.rmdir(lock_dir_path)


def rundb_filename_for_schema_version(schema_version: Tuple[int]) -> str:
    return RUNDB_FILE_NAME_TEMPLATE.format('.'.join([str(c) for c in schema_version]))


def prepare_locked_working_tree(root_path: fs.Path, rundb_schema_version: Tuple[int], max_dependency_age):
    rundb_filename = rundb_filename_for_schema_version(rundb_schema_version)
    management_tree_path = os.path.join(str(root_path.native), MANAGEMENTTREE_DIR_NAME)
    temp_path_provider = UniquePathProvider(root_path / f'{MANAGEMENTTREE_DIR_NAME}/{TEMPORARY_DIR_NAME}/')

    try:
        temporary_path = str(temp_path_provider.root_path.native)
        remove_filesystem_object(temporary_path, ignore_non_existent=True)
        os.mkdir(temporary_path)
        rundb_path = os.path.join(management_tree_path, rundb_filename)
        try:
            mode = os.lstat(rundb_path).st_mode
            if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                remove_filesystem_object(rundb_path)
        except FileNotFoundError:
            pass

        # prepare o for mtime probing
        mtime_probe_path = os.path.join(management_tree_path, MTIME_PROBE_FILE_NAME)
        mtime_probeu_path = os.path.join(management_tree_path, MTIME_PROBE_FILE_NAME.upper())
        remove_filesystem_object(mtime_probe_path, ignore_non_existent=True)
        remove_filesystem_object(mtime_probeu_path, ignore_non_existent=True)

        mtime_probe = open(mtime_probe_path, 'xb')  # always a fresh file (no link to an existing one)

        try:
            probe_stat = os.lstat(mtime_probe_path)
            try:
                probeu_stat = os.lstat(mtime_probeu_path)
            except FileNotFoundError:
                is_working_tree_case_sensitive = True
            else:
                is_working_tree_case_sensitive = not os.path.samestat(probe_stat, probeu_stat)

            db = _rundb.Database(rundb_path, max_dependency_age,
                                 f"if you suspect database corruption, remove the run-database file(s): {rundb_path!r}")
        except:
            mtime_probe.close()
            raise

    except _error.DatabaseError as e:
        # _rundb.DatabaseError on error may have multi-line message
        raise _error.ManagementTreeError(str(e)) from None
    except OSError as e:
        msg = (
            f'failed to setup management tree for {root_path.as_string()!r}\n'
            f'  | reason: {ut.exception_to_line(e)}'  # only first line
        )
        raise _error.ManagementTreeError(msg) from None

    return temp_path_provider, mtime_probe, db, is_working_tree_case_sensitive
