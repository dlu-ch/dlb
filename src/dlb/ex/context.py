# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Execution contexts for tool instances."""

__all__ = (
    'Context',
    'ContextNestingError',
    'NotRunningError',
    'ManagementTreeError',
    'NoWorkingTreeError',
    'WorkingTreeTimeError',
    'NonActiveContextAccessError'
)

import sys
import re
import os
import os.path
import stat
import time
import tempfile
import asyncio
from typing import Pattern, Type, Optional, Dict, Union
from .. import ut
from .. import fs
from ..fs import manip
from . import rundb
from . import aseq
assert sys.version_info >= (3, 7)


_contexts = []


def _get_root_specifics():
    if not _contexts:
        raise NotRunningError
    # noinspection PyProtectedMember
    return _contexts[0]._root_specifics


class ContextNestingError(Exception):
    pass


class NotRunningError(Exception):
    pass


class ManagementTreeError(Exception):
    pass


class NoWorkingTreeError(Exception):
    pass


class WorkingTreeTimeError(Exception):
    pass


class NonActiveContextAccessError(Exception):
    pass


# a directory containing a directory with this name is considered a working tree of dlb
_MANAGEMENTTREE_DIR_NAME = '.dlbroot'

# a directory containing a directory with this name is considered a working tree of dlb
_MTIME_PROBE_FILE_NAME = 'o'
assert _MTIME_PROBE_FILE_NAME.upper() != _MTIME_PROBE_FILE_NAME

_LOCK_DIRNAME = 'lock'
_MTIME_TEMPORARY_DIR_NAME = 't'
_RUNDB_FILE_NAME = 'runs.sqlite'


class _EnvVarDict:

    def __init__(self, parent=None, top_value_by_name: Optional[Dict[str, str]] = None):
        if not (parent is None or isinstance(parent, _EnvVarDict)):
            raise TypeError

        self._parent = parent
        if parent is None:
            self._top_value_by_name = {str(k): str(v) for k, v, in top_value_by_name.items()}
            self._value_by_name = dict()
        else:
            self._top_value_by_name = dict()
            self._value_by_name = dict(parent._value_by_name)
        self._restriction_by_name: Dict[str, Pattern] = dict()

    def import_from_outer(self, name: str, restriction: Union[str, Pattern], example: str):
        self._check_non_empty_str(name=name)

        if isinstance(restriction, str):
            restriction = re.compile(restriction)
        if not isinstance(restriction, Pattern):
            raise TypeError("'restriction' must be regular expression (compiled or str)")
        if not isinstance(example, str):
            raise TypeError("'example' must be a str")

        if not restriction.fullmatch(example):
            raise ValueError(f"'example' is invalid with respect to 'restriction': {example!r}")

        self._check_if_env_of_active_context()

        value = self._value_by_name.get(name)
        if value is None:
            # import from innermost outer context that has the environment variable defined
            value = (self._parent._value_by_name if self._parent else self._top_value_by_name).get(name)
            value_name = 'imported'
        else:
            value_name = 'current'

        if value is not None:
            if not restriction.fullmatch(value):
                raise ValueError(f"{value_name} value invalid with respect to 'restriction': {value!r}")

        self._restriction_by_name[name] = restriction  # cannot be removed, once defined!
        if value is not None:
            self._value_by_name[name] = value

    def is_imported(self, name):
        self._check_non_empty_str(name=name)
        if name in self._restriction_by_name:
            return True
        return self._parent is not None and self._parent.is_imported(name)

    def _is_valid(self, name, value):
        self._check_non_empty_str(name=name)
        restriction = self._restriction_by_name.get(name)
        if restriction is not None and not restriction.fullmatch(value):
            return False
        return self._parent is None or self._parent._is_valid(name, value)

    @staticmethod
    def _check_non_empty_str(**kwargs):
        for k, v in kwargs.items():
            if not isinstance(v, str):
                raise TypeError(f"{k!r} must be a str")
            if not v:
                raise ValueError(f"{k!r} must not be empty")

    def _check_if_env_of_active_context(self):
        if not (_contexts and _contexts[-1].env is self):
            msg = (
                "'env' of an inactive context must not be modified\n"
                "  | use 'dlb.ex.Context.active.env' to get 'env' of the active context"
            )
            raise NonActiveContextAccessError(msg)

    # dictionary methods

    def get(self, name: str, default=None):
        self._check_non_empty_str(name=name)
        return self._value_by_name.get(name, default)

    def items(self):
        return self._value_by_name.items()

    def __len__(self):
        return self._value_by_name.__len__()

    def __getitem__(self, name: str) -> str:
        value = self.get(name)
        if value is None:
            msg = (
                f"not a defined environment variable in the context: {name!r}\n"
                f"  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...]' = ..."
            )
            raise KeyError(msg)
        return value

    def __setitem__(self, name: str, value: str):
        self._check_non_empty_str(name=name)
        if not isinstance(value, str):
            raise TypeError("'value' must be a str")

        if not self.is_imported(name):
            msg = (
                f"environment variable not imported into context: {name!r}\n"
                f"  | use 'dlb.ex.Context.active.env.import_from_outer()' first"
            )
            raise AttributeError(msg)

        self._check_if_env_of_active_context()

        if not self._is_valid(name, value):
            raise ValueError(f"'value' invalid with respect to active or an outer context: {value!r}")

        self._value_by_name[name] = value

    def __delitem__(self, name):
        self._check_non_empty_str(name=name)
        self._check_if_env_of_active_context()
        try:
            del self._value_by_name[name]
        except KeyError:
            raise KeyError(f"not a defined environment variable in the context: {name!r}") from None

    def __iter__(self):
        return self._value_by_name.__iter__()

    def __contains__(self, name):
        return self._value_by_name.__contains__(name)


class _ContextMeta(type):
    def __getattribute__(self, name):
        refer = not name.startswith('_')
        try:
            a = super().__getattribute__(name)
            refer = refer and isinstance(a, property)
        except AttributeError:
            if not refer:
                raise
        if refer:
            if not _contexts:
                raise NotRunningError
            a = getattr(_contexts[-1], name)  # delegate to active context

        # noinspection PyUnboundLocalVariable
        return a

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise AttributeError("public attributes of 'dlb.ex.Context' are read-only")
        return super().__setattr__(key, value)


class _RootSpecifics:
    def __init__(self, path_cls: Type[fs.Path]):
        self._path_cls = path_cls

        # cwd must be a working tree`s root

        working_tree_path = os.getcwd()
        # TODO check if canonical-case path

        try:
            self._working_tree_path = path_cls(path_cls.Native(working_tree_path), is_dir=True)
        except (ValueError, OSError) as e:
            msg = (  # assume that ut.exception_to_string(e) contains the working_tree_path
                f'current directory violates imposed path restrictions\n'
                f'  | reason: {ut.exception_to_line(e)}\n'
                f'  | move the working directory or choose a less restrictive path class for the root context'
            )
            raise ValueError(msg) from None

        self._working_tree_path_native = self._working_tree_path.native

        # from pathlib.py of Python 3.7.3:
        # "NOTE: according to POSIX, getcwd() cannot contain path components which are symlinks."

        working_tree_path = str(self._working_tree_path_native)

        try:
            # may raise FileNotFoundError, RuntimeError
            real_working_tree_path = self._working_tree_path_native.raw.resolve(strict=True)
            if not os.path.samefile(str(real_working_tree_path), working_tree_path):
                raise ValueError
        except (ValueError, OSError, RuntimeError):
            msg = (
                f"supposedly equivalent forms of current directory's path point to different filesystem objects\n"
                f'  | reason: unresolved symbolic links, dlb bug, Python bug or a moved directory\n'
                f'  | try again?'
            )
            raise ValueError(msg) from None

        self._is_working_tree_case_sensitive = True
        self._mtime_probe = None
        self._rundb = None

        management_tree_path = os.path.join(working_tree_path, _MANAGEMENTTREE_DIR_NAME)

        # 1. is this a working tree?

        msg = (
            f'current directory is no working tree: {str(working_tree_path)!r}\n'
            f'  | reason: does not contain a directory {_MANAGEMENTTREE_DIR_NAME!r} (that is not a symbolic link)'
        )
        try:
            mode = os.lstat(management_tree_path).st_mode
        except Exception:
            raise NoWorkingTreeError(msg) from None
        if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
            raise NoWorkingTreeError(msg) from None

        # TODO make sure the "calling" source file is in the managed tree

        # 2. if yes: lock it

        lock_dir_path = os.path.join(management_tree_path, _LOCK_DIRNAME)
        try:
            try:
                mode = os.lstat(lock_dir_path).st_mode
                if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
                    manip.remove_filesystem_object(lock_dir_path)
            except FileNotFoundError:
                pass
            os.mkdir(lock_dir_path)
        except OSError as e:
            msg = (
                f'cannot acquire lock for exclusive access to working tree {working_tree_path!r}\n'
                f'  | reason: {ut.exception_to_line(e)}\n'
                f'  | to break the lock (if you are sure no other dlb process is running): '
                f'remove {lock_dir_path!r}'
            )
            raise ManagementTreeError(msg)

        # 3. then prepare it

        try:  # OSError in this block -> ManagementTreeError
            try:
                # prepare o for mtime probing
                mtime_probe_path = os.path.join(management_tree_path, _MTIME_PROBE_FILE_NAME)
                mtime_probeu_path = os.path.join(management_tree_path, _MTIME_PROBE_FILE_NAME.upper())
                manip.remove_filesystem_object(mtime_probe_path, ignore_non_existing=True)
                manip.remove_filesystem_object(mtime_probeu_path, ignore_non_existing=True)

                self._mtime_probe = open(mtime_probe_path, 'xb')  # always a fresh file (no link to an existing one)
                probe_stat = os.lstat(mtime_probe_path)
                try:
                    probeu_stat = os.lstat(mtime_probeu_path)
                except FileNotFoundError:
                    pass
                else:
                    self._is_working_tree_case_sensitive = not os.path.samestat(probe_stat, probeu_stat)

                temporary_path = os.path.join(management_tree_path, _MTIME_TEMPORARY_DIR_NAME)
                manip.remove_filesystem_object(temporary_path, ignore_non_existing=True)
                os.mkdir(temporary_path)

                rundb_path = os.path.join(management_tree_path, _RUNDB_FILE_NAME)
                try:
                    mode = os.lstat(rundb_path).st_mode
                    if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                        manip.remove_filesystem_object(rundb_path)
                except FileNotFoundError:
                    pass

                suggestion_if_database_error = \
                    f"if you suspect database corruption, remove the run-database file(s): {rundb_path!r}"
                self._rundb = rundb.Database(rundb_path, suggestion_if_database_error)
            except Exception:
                self._close_and_unlock_if_open()
                raise
        except rundb.DatabaseError as e:
            # rundb.DatabaseError on error may have multi-line message
            raise ManagementTreeError(str(e)) from None
        except OSError as e:
            msg = (
                f'failed to setup management tree for {working_tree_path!r}\n'
                f'  | reason: {ut.exception_to_line(e)}'  # only first line
            )
            raise ManagementTreeError(msg) from None

    @property
    def root_path(self) -> fs.Path:
        return self._working_tree_path

    def create_temporary(self, suffix='', prefix='t', is_dir=False) -> fs.Path:
        if not isinstance(suffix, str) or not isinstance(prefix, str):
            raise TypeError("'prefix' and 'suffix' must be str")
        if not prefix:
            raise ValueError("'prefix' must not be empty")
        if os.path.sep in prefix or (os.path.altsep and os.path.altsep in prefix):
            raise ValueError("'prefix' must not contain a path separator")
        if os.path.sep in suffix or (os.path.altsep and os.path.altsep in suffix):
            raise ValueError("'prefix' must not contain a path separator")

        t = os.path.join(str(self._working_tree_path_native), _MANAGEMENTTREE_DIR_NAME, _MTIME_TEMPORARY_DIR_NAME)
        is_dir = bool(is_dir)
        if is_dir:
            p_str = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=t)
        else:
            fd, p_str = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=t)
            os.close(fd)
        return fs.Path(fs.Path.Native(p_str), is_dir=is_dir)

    @property
    def working_tree_time_ns(self) -> int:
        self._mtime_probe.seek(0)
        self._mtime_probe.write(b'0')  # updates mtime
        return os.fstat(self._mtime_probe.fileno()).st_mtime_ns

    def managed_tree_path_of(self, path, *, is_dir: Optional[bool] = None,
                             existing: bool = False, collapsable: bool = False) -> fs.Path:
        # this must be very fast for relative dlb.fs.Path with existing = True

        if not isinstance(path, fs.Path) or is_dir is not None and is_dir != path.is_dir():
            path = fs.Path(path, is_dir=is_dir)

        if path.is_absolute():
            # note: do _not_ used path.resolve() or os.path.realpath(), since it would resolve the entire path
            native_components = path.native.components

            # may raise PathNormalizationError
            normalized_native_components = \
                (native_components[0],) + \
                manip.normalize_dotdot_native_components(native_components[1:], ref_dir_path=native_components[0])

            native_root_path_components = self._working_tree_path_native.components
            n = len(native_root_path_components)
            if normalized_native_components[:n] != native_root_path_components:
                raise manip.PathNormalizationError("does not start with the working tree's root path")

            rel_components = ('',) + normalized_native_components[n:]
        else:
            # 'collapsable' means only the part relative to the working tree's root
            ref_dir_path = None if collapsable else str(self._working_tree_path_native)
            rel_components = ('',) + manip.normalize_dotdot_native_components(
                path.components[1:], ref_dir_path=ref_dir_path)

        if len(rel_components) >= 2 and rel_components[1] in ('..', _MANAGEMENTTREE_DIR_NAME):
            raise ValueError(f'path not in managed tree: {path.as_string()!r}') from None

        # may raise ValueError
        rel_path = path.__class__(rel_components, is_dir=path.is_dir()) if path.components != rel_components else path

        if not existing:
            try:
                sr = os.lstat(os.path.sep.join([str(self._working_tree_path_native), str(rel_path.native)]))
                is_dir = stat.S_ISDIR(sr.st_mode)
            except OSError as e:
                raise manip.PathNormalizationError(oserror=e) from None
            if is_dir != rel_path.is_dir():
                rel_path = path.__class__(rel_components, is_dir=is_dir)

        return rel_path

    def _cleanup(self):
        self._rundb.cleanup()
        self._rundb.commit()
        temporary_path = os.path.join(str(self._working_tree_path_native),
                                      _MANAGEMENTTREE_DIR_NAME, _MTIME_TEMPORARY_DIR_NAME)
        manip.remove_filesystem_object(temporary_path, ignore_non_existing=True)

    def _cleanup_and_delay_to_working_tree_time_change(self):
        t0 = time.monotonic_ns()  # since Python 3.7
        wt0 = self.working_tree_time_ns
        self._cleanup()  # seize the the day
        while True:
            wt = self.working_tree_time_ns
            if wt != wt0:  # guarantee G-T2
                break
            if (time.monotonic_ns() - t0) / 1e9 > 10.0:  # at most 10 for s
                msg = (
                    'working tree time did not change for at least 10 s of system time\n'
                    '  | was the system time adjusted in this moment?'
                )
                raise WorkingTreeTimeError(msg)
            time.sleep(0.015)  # typical effective working tree time resolution: 10 ms

    def _close_and_unlock_if_open(self):  # safe to call multiple times
        # called while self is not an active context (note: an exception may already have happened)
        most_serious_exception = None

        if self._mtime_probe:
            try:
                self._mtime_probe.close()
            except Exception as e:
                most_serious_exception = e
            self._mtime_probe = None

        lock_dir_path = os.path.join(str(self._working_tree_path_native), _MANAGEMENTTREE_DIR_NAME, _LOCK_DIRNAME)
        try:
            os.rmdir(lock_dir_path)  # unlock
        except Exception as e:
            most_serious_exception = e

        if self._rundb:
            try:
                self._rundb.close()  # note: uncommitted changes are lost!
            except Exception as e:
                most_serious_exception = e
            self._rundb = None

        if most_serious_exception:
            raise most_serious_exception

    def _cleanup_and_close(self):  # "normal" exit of root context (as far as it is special for root context)
        first_exception = None

        try:
            self._cleanup_and_delay_to_working_tree_time_change()
        except Exception as e:
            first_exception = e

        try:
            self._close_and_unlock_if_open()
        except Exception as e:
            first_exception = e

        if first_exception:
            if isinstance(first_exception, (OSError, rundb.DatabaseError)):
                msg = (
                    f'failed to cleanup management tree for {str(self._working_tree_path.native)!r}\n'
                    f'  | reason: {ut.exception_to_line(first_exception)}'
                )
                raise ManagementTreeError(msg) from None
            else:
                raise first_exception


_EnvVarDict.__name__ = 'EnvVarDict'
_EnvVarDict.__qualname__ = 'Context.EnvVarDict'
ut.set_module_name_to_parent(_EnvVarDict)


class Context(metaclass=_ContextMeta):

    EnvVarDict = NotImplemented  # only Context should construct an _EnvVarDict

    def __init__(self, *, path_cls: Type[fs.Path] = fs.Path):
        if not (isinstance(path_cls, type) and issubclass(path_cls, fs.Path)):
            raise TypeError("'path_cls' must be a subclass of 'dlb.fs.Path'")
        self._path_cls = path_cls
        self._redo_sequencer = aseq.LimitingCoroutineSequencer(asyncio.get_event_loop())
        self._root_specifics: Optional[_RootSpecifics] = None
        self._env: Optional[_EnvVarDict] = None

    @property
    def active(self):
        if not _contexts:
            raise NotRunningError
        return _contexts[-1]

    @property
    def path_cls(self) -> Type[fs.Path]:
        return self._path_cls

    @property
    def env(self) -> _EnvVarDict:
        # noinspection PyStatementEffect
        self.active
        return self._env

    @property
    def redo_sequencer(self) -> aseq.LimitingCoroutineSequencer:
        return self._redo_sequencer

    def __getattr__(self, name):
        try:
            if name.startswith('_'):
                raise AttributeError
            return getattr(_get_root_specifics(), name)  # delegate to _RootSpecifics
        except AttributeError:
            raise AttributeError(f'{self.__class__.__qualname__!r} object has no attribute {name!r}') from None

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise AttributeError("public attributes of 'dlb.ex.Context' instances are read-only")
        return super().__setattr__(key, value)

    def __enter__(self):
        if _contexts:
            try:
                # noinspection PyCallingNonCallable
                self._path_cls(self.root_path)
            except ValueError as e:
                msg = (  # assume that ut.exception_to_string(e) contains the working_tree_path
                    f"working tree's root path violates path restrictions imposed by this context\n"
                    f'  | reason: {ut.exception_to_line(e)}\n'
                    f'  | move the working directory or choose a less restrictive path class for the root context'
                )
                raise ValueError(msg) from None
            self._env = _EnvVarDict(_contexts[-1].env, None)
        else:
            self._root_specifics = _RootSpecifics(self._path_cls)
            self._env = _EnvVarDict(None, os.environ)
        _contexts.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._redo_sequencer.cancel_all(timeout=None)
        if not (_contexts and _contexts[-1] == self):
            raise ContextNestingError
        _contexts.pop()
        self._env = None
        if self._root_specifics:
            # noinspection PyProtectedMember
            self._root_specifics._cleanup_and_close()
            self._root_specifics = None


def _get_rundb() -> rundb.Database:
    # use this to access the database from dlb.ex.Tool
    # noinspection PyProtectedMember,PyUnresolvedReferences
    db = _get_root_specifics()._rundb
    if db is None:
        raise ValueError('run-database not open')
    return db


ut.set_module_name_to_parent_by_name(vars(), __all__)
