# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Execution contexts for tool instances.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = ['Context', 'ReadOnlyContext']

import re
import os
import os.path
import stat
import time
import datetime
from typing import Collection, Dict, Hashable, Iterable, List, Mapping, Optional, Pattern, Tuple, Type, Union

from .. import ut
from .. import di
from .. import fs
from .. import cf
from . import _error
from . import _rundb
from . import _worktree

_contexts: List['Context'] = []


def _get_root_specifics() -> '_RootSpecifics':
    if not _contexts:
        raise _error.NotRunningError
    # noinspection PyProtectedMember
    return _contexts[0]._root_specifics


def _get_rundb() -> _rundb.Database:
    # use this to access the database from dlb.ex.Tool
    # noinspection PyProtectedMember,PyUnresolvedReferences
    db = _get_root_specifics()._rundb
    return db


def _register_successful_run(with_redo: bool):
    rs = _get_root_specifics()
    if with_redo:
        # noinspection PyProtectedMember
        rs._successful_redo_run_count += 1
    else:
        # noinspection PyProtectedMember
        rs._successful_nonredo_run_count += 1


class _BaseEnvVarDict:

    def __init__(self, context: 'Context', top_value_by_name: Mapping[str, str]):
        # these objects must not be replaced once constructed (only modified)
        # reason: read-only view

        self._context = context
        self._top_value_by_name = {str(k): str(v) for k, v, in top_value_by_name.items()}
        self._value_by_name = {} if context.parent is None else dict(context.parent.env._value_by_name)
        self._pattern_by_name: Dict[str, Pattern] = {}

    def is_imported(self, name):
        self._check_non_empty_str(name=name)
        if name in self._pattern_by_name:
            return True
        return self._context.parent is not None and self._context.parent.env.is_imported(name)

    def _find_violated_validation_pattern(self, name, value) -> Optional[Pattern]:
        pattern = self._pattern_by_name.get(name)
        if pattern is not None and not pattern.fullmatch(value):
            return pattern
        if self._context.parent is None:
            return
        return self._context.parent.env._find_violated_validation_pattern(name, value)

    @staticmethod
    def _check_non_empty_str(**kwargs):
        for k, v in kwargs.items():
            if not isinstance(v, str):
                raise TypeError(f"{k!r} must be a str")
            if not v:
                raise ValueError(f"{k!r} must not be empty")

    def __repr__(self) -> str:
        items = sorted(self.items())
        args = ', '.join('{}: {}'.format(repr(k), repr(v)) for k, v in items)
        return f"{self.__class__.__name__}({{{args}}})"

    # dictionary methods

    def get(self, name: str, default=None):
        self._check_non_empty_str(name=name)
        return self._value_by_name.get(name, default)

    def items(self):
        return self._value_by_name.items()

    def __len__(self) -> int:
        return self._value_by_name.__len__()

    def __getitem__(self, name: str) -> str:
        value = self.get(name)
        if value is None:
            msg = (
                f"not a defined environment variable in the context: {name!r}\n"
                f"  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...] = ...'"
            )
            raise KeyError(msg)
        return value

    def __iter__(self):
        return self._value_by_name.__iter__()

    def __contains__(self, name) -> bool:
        return self._value_by_name.__contains__(name)


class _EnvVarDict(_BaseEnvVarDict):

    def import_from_outer(self, name: str, *, pattern: Union[str, Pattern], example: str):
        self._check_non_empty_str(name=name)

        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        if not isinstance(pattern, Pattern):
            raise TypeError("'pattern' must be regular expression (compiled or str)")
        if not isinstance(example, str):
            raise TypeError("'example' must be a str")

        if not pattern.fullmatch(example):
            raise ValueError(f"'example' is not matched by 'pattern': {example!r}")

        self._prepare_for_modification()

        value = self._value_by_name.get(name)
        if value is None:
            # import from innermost outer context that has the environment variable defined
            d = self._context.parent.env._value_by_name if self._context.parent else self._top_value_by_name
            value = d.get(name)
            value_name = 'imported'
        else:
            value_name = 'current'

        if value is not None and not pattern.fullmatch(value):
            raise ValueError(f"{value_name} value is not matched by 'pattern': {value!r}")

        self._pattern_by_name[name] = pattern  # cannot be removed, once defined!
        if value is not None:
            self._value_by_name[name] = value

    def _prepare_for_modification(self):
        if not (_contexts and _contexts[-1] is self._context):
            msg = (
                "'env' of an inactive context must not be modified\n"
                "  | use 'dlb.ex.Context.active.env' to get 'env' of the active context"
            )
            raise _error.ContextModificationError(msg)
        self._context.complete_pending_redos()

    # dictionary methods

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

        self._prepare_for_modification()

        regex = self._find_violated_validation_pattern(name, value)
        if regex is not None:
            msg = (
                f"'value' is not matched by associated validation pattern: {value!r}\n"
                f"  | validation pattern in question is {regex.pattern!r}"
            )
            raise ValueError(msg)

        self._value_by_name[name] = value

    def __delitem__(self, name):
        self._check_non_empty_str(name=name)
        self._prepare_for_modification()
        try:
            del self._value_by_name[name]
        except KeyError:
            raise KeyError(f"not a defined environment variable in the context: {name!r}") from None


_EnvVarDict.__name__ = 'EnvVarDict'
_EnvVarDict.__qualname__ = 'Context.EnvVarDict'
ut.set_module_name_to_parent(_EnvVarDict)


class _ReadOnlyEnvVarDictView(_BaseEnvVarDict):

    # noinspection PyMissingConstructor
    def __init__(self, env_var_dict: _EnvVarDict):
        self._context = env_var_dict._context
        self._top_value_by_name = env_var_dict._top_value_by_name
        self._value_by_name = env_var_dict._value_by_name
        self._pattern_by_name = env_var_dict._pattern_by_name


_ReadOnlyEnvVarDictView.__name__ = 'ReadOnlyEnvVarDictView'
_ReadOnlyEnvVarDictView.__qualname__ = 'Context.ReadOnlyEnvVarDictView'
ut.set_module_name_to_parent(_ReadOnlyEnvVarDictView)


class _BaseHelperDict:

    def __init__(self, context: 'Context', implicit_abs_path_by_helper_path: Optional[Dict[fs.Path, fs.Path]]):
        # a 'self.get(helper_path)' or 'self[help_path]' tries these steps in order until the result is not None
        #
        #     1. self._explicit_abs_path_by_helper_path.get(helper_path)
        #     2  self._implicit_abs_path_by_helper_path.get(helper_path) if implicit_abs_path_by_helper_path is not None
        #     3. context.find_in_path(helper_path) if implicit_abs_path_by_helper_path is not None
        #
        # When the absolute path 'abs_path' for a helper path is found in step 3, its it added to
        # self._implicit_abs_path_by_helper_path:
        #
        #     self._implicit_abs_path_by_helper_path[helper_path] = [abs_path

        # these objects must not be replaced once constructed (only modified)
        # reason: read-only view

        self._context = context
        self._explicit_abs_path_by_helper_path: Dict[fs.Path, fs.Path] = \
            {} if context.parent is None else dict(context.parent.helper._explicit_abs_path_by_helper_path)

        self._implicit_abs_path_by_helper_path = implicit_abs_path_by_helper_path

    def __repr__(self) -> str:
        items = sorted(self.items())
        args = ', '.join('{}: {}'.format(repr(k.as_string()), repr(v.as_string())) for k, v in items)
        return f"{self.__class__.__name__}({{{args}}})"

    # dictionary methods

    def keys(self) -> Collection[fs.Path]:
        if not self._implicit_abs_path_by_helper_path:
            return tuple(self._explicit_abs_path_by_helper_path)
        return frozenset(self._explicit_abs_path_by_helper_path) | frozenset(self._implicit_abs_path_by_helper_path)

    def items(self) -> Collection[Tuple[fs.Path, fs.Path]]:
        return tuple((k, self[k]) for k in self.keys())

    def get(self, helper_path: fs.PathLike):
        if not isinstance(helper_path, fs.Path):
            helper_path = fs.Path(helper_path)
        p = self._explicit_abs_path_by_helper_path.get(helper_path)
        if p is not None:
            return p
        if self._implicit_abs_path_by_helper_path is None:
            return None
        p = self._implicit_abs_path_by_helper_path.get(helper_path)
        if p is not None:
            return p
        p = self._context.find_path_in(helper_path)
        if p is not None:
            self._implicit_abs_path_by_helper_path[helper_path] = p
            return p

    def __len__(self) -> int:
        return len(self.keys())

    def __getitem__(self, helper_path: fs.PathLike) -> fs.Path:
        p = self.get(helper_path)
        if p is None:
            msg = (
                f"not a known dynamic helper in the context: {helper_path!r}\n"
                f"  | use 'dlb.ex.Context.active.helper[...] = ...'"
            )
            raise KeyError(msg)
        return p

    def __iter__(self):
        return (k for k in self.keys())

    def __contains__(self, helper_path: fs.PathLike) -> bool:
        if not isinstance(helper_path, fs.Path):
            helper_path = fs.Path(helper_path)
        if helper_path in self._explicit_abs_path_by_helper_path:
            return True
        if self._implicit_abs_path_by_helper_path is None:
            return False
        return helper_path in self._implicit_abs_path_by_helper_path


class _HelperDict(_BaseHelperDict):

    def _prepare_for_modification(self):
        if not (_contexts and _contexts[-1] is self._context):
            msg = (
                "'helper' of an inactive context must not be modified\n"
                "  | use 'dlb.ex.Context.active.helper' to get 'helper' of the active context"
            )
            raise _error.ContextModificationError(msg)
        self._context.complete_pending_redos()

    def __setitem__(self, helper_path: fs.PathLike, abs_path: fs.PathLike):
        if not isinstance(helper_path, fs.Path):
            helper_path = fs.Path(helper_path)
        if helper_path.is_absolute():
            raise ValueError("'helper_path' must not be absolute")
        if not isinstance(abs_path, fs.Path):
            abs_path = fs.Path(abs_path)
        if not abs_path.is_absolute():
            abs_path = self._context.root_path / abs_path
        if abs_path.is_dir() != helper_path.is_dir():
            t = 'directory' if helper_path.is_dir() else 'non-directory'
            msg = f"when 'helper_path' is a {t}, 'abs_path' must also be a {t}"
            raise ValueError(msg)

        self._prepare_for_modification()
        self._explicit_abs_path_by_helper_path[helper_path] = abs_path


class _ReadOnlyHelperDictView(_BaseHelperDict):

    # noinspection PyMissingConstructor
    def __init__(self, helper_dict: _HelperDict):
        self._context = helper_dict._context
        self._explicit_abs_path_by_helper_path = helper_dict._explicit_abs_path_by_helper_path
        self._implicit_abs_path_by_helper_path = helper_dict._implicit_abs_path_by_helper_path


_HelperDict.__name__ = 'HelperDict'
_HelperDict.__qualname__ = 'Context.HelperDict'
ut.set_module_name_to_parent(_HelperDict)


class _BaseContextMeta(type):
    def __setattr__(cls, key, value):
        if not key.startswith('_'):
            name = f'{cls.__module__}.{cls.__qualname__}'
            raise AttributeError(f'public attributes of {name!r} are read-only')
        return super().__setattr__(key, value)


class _ContextMeta(_BaseContextMeta):

    # As of PyCharm 2020.1, the type hint is not enough to enable code completion.
    # There is also a dummy attribute Context.active with the same type hint.

    @property
    def active(cls) -> 'Context':
        if not _contexts:
            raise _error.NotRunningError
        return _contexts[-1]


def _show_summary(summaries: List[Tuple[datetime.datetime, int, int, int]]):
    # last element of *summaries* is summary of just completed dlb run

    _, duration_ns, _, _ = summaries[-1]

    mean_duration_ns = 0
    if len(summaries) > 1:
        mean_duration_ns = sum(d for _, d, _, _ in summaries[:-1]) // len(summaries)
    if mean_duration_ns > 0:
        msg = (
            f'duration compared to mean duration of previous {len(summaries) - 1} successful runs: '
            f'{100 * duration_ns / mean_duration_ns:.1f}% of {di.format_time_ns(mean_duration_ns)} seconds\n'
        )
    else:
        msg = f'duration: {di.format_time_ns(duration_ns)} s\n'

    msg += '    start  \tseconds  \truns\b  redos\b'
    for i, (start_time, duration_ns, runs, redos) in enumerate(summaries):
        current_mark = '*' if i == len(summaries) - 1 else ''
        start_time = start_time.isoformat() + 'Z'
        duration_ns = di.format_time_ns(duration_ns)
        msg += f'\n    {start_time}{current_mark}  \t{duration_ns}  \t{runs}\b  {redos}\b'
        if runs > 0:
            redo_ratio_percent = 100 * redos / runs
            msg += f' ({redo_ratio_percent:.1f}%)\b'
    di.inform(msg, level=cf.level.run_summary)


class _RootSpecifics:
    def __init__(self, path_cls: Type[fs.Path]):
        self._implicit_abs_path_by_helper_path: Dict[fs.Path, fs.Path] = {}
        self._path_cls = path_cls

        self._successful_redo_run_count = 0
        self._successful_nonredo_run_count = 0

        # 1. check if the process' working directory is a working tree`s root

        self._root_path = _worktree.get_checked_root_path_from_cwd(os.getcwd(), path_cls)
        root_path = str(self._root_path.native)
        self._root_path_native_str = root_path
        # TODO make sure the "calling" source file is in the managed tree

        # path of all existing directories in os.get_exec_path(), that can be represented as dlb.fs.Path
        executable_search_paths = []
        for p in os.get_exec_path():  # do _not_ expand a leading '~'
            try:
                pn = fs.Path.Native(p)
                if p and os.path.isdir(pn):
                    p = fs.Path(pn, is_dir=True)
                    if not p.is_absolute():
                        p = self._root_path / p
                    if p not in executable_search_paths:
                        executable_search_paths.append(p)
            except (OSError, ValueError):
                pass
        self._executable_search_paths = tuple(executable_search_paths)

        # 2. if yes: lock it

        _worktree.lock_working_tree(self._root_path)

        # 3. then prepare it

        self._temp_path_provider = None
        self._mtime_probe = None
        self._rundb = None
        try:
            if not isinstance(cf.max_dependency_age, datetime.timedelta):
                raise TypeError("'dlb.cf.max_dependency_age' must be a datetime.timedelta object")
            if not cf.max_dependency_age > datetime.timedelta(0):
                raise ValueError("'dlb.cf.max_dependency_age' must be positive")
            self._temp_path_provider, self._mtime_probe, self._rundb, self._is_working_tree_case_sensitive = \
                _worktree.prepare_locked_working_tree(self._root_path, _rundb.SCHEMA_VERSION, cf.max_dependency_age)
        except BaseException:
            self._close_and_unlock_if_open()
            raise

    @property
    def working_tree_time_ns(self) -> int:
        self._mtime_probe.seek(0)
        self._mtime_probe.write(b'0')  # updates mtime
        return os.fstat(self._mtime_probe.fileno()).st_mtime_ns

    def _cleanup(self):
        self._rundb.cleanup()
        self._rundb.commit()
        _worktree.remove_filesystem_object(str(self._temp_path_provider.root_path.native), ignore_non_existent=True)

    def _cleanup_and_delay_to_working_tree_time_change(self, was_successful: bool):
        t0 = time.monotonic_ns()  # since Python 3.7
        wt0 = self.working_tree_time_ns
        if was_successful:
            summary = self._rundb.update_run_summary(self._successful_nonredo_run_count,
                                                     self._successful_redo_run_count)
            try:
                if cf.latest_run_summary_max_count > 0 and di.is_unsuppressed_level(cf.level.run_summary):
                    summaries = self._rundb.get_latest_successful_run_summaries(cf.latest_run_summary_max_count)
                    _show_summary(summaries + [summary])
            except (TypeError, ValueError):
                pass  # ignore most common exceptions for invalid cf.latest_run_summary_max_count, cf.level.*
        self._cleanup()  # seize the day
        while True:
            wt = self.working_tree_time_ns
            if wt != wt0:  # guarantee G-T2
                break
            if (time.monotonic_ns() - t0) / 1e9 > 10.0:  # at most 10 s
                msg = (
                    'working tree time did not change for at least 10 s of system time\n'
                    '  | was the system time adjusted in this moment?'
                )
                raise _error.WorkingTreeTimeError(msg)
            time.sleep(0.015)  # typical effective working tree time resolution: 10 ms

    def _close_and_unlock_if_open(self):  # safe to call multiple times
        # called while self is not an active context (note: an exception may already have happened)
        most_serious_exception = None

        if self._mtime_probe:
            try:
                self._mtime_probe.close()
            except BaseException as e:
                most_serious_exception = e
            self._mtime_probe = None

        if self._rundb:
            try:
                self._rundb.close()  # note: uncommitted changes are lost!
            except BaseException as e:
                most_serious_exception = e
            self._rundb = None

        try:
            _worktree.unlock_working_tree(self._root_path)
        except BaseException as e:
            if most_serious_exception is None:
                most_serious_exception = e

        if most_serious_exception:
            raise most_serious_exception

    def _cleanup_and_close(self, was_successful: bool):
        # "normal" exit of root context (as far as it is special for root context)
        first_exception = None

        try:
            self._cleanup_and_delay_to_working_tree_time_change(was_successful)
        except BaseException as e:
            first_exception = e

        try:
            self._close_and_unlock_if_open()
        except BaseException as e:
            first_exception = e

        if first_exception:
            msg = (
                f'failed to cleanup management tree for {str(self._root_path.native)!r}\n'
                f'  | reason: {ut.exception_to_line(first_exception)}'
            )
            raise _error.ManagementTreeError(msg) from None


class _BaseContext(metaclass=_BaseContextMeta):

    # only Context should construct instances of these:
    EnvVarDict = NotImplemented
    ReadOnlyEnvVarDictView = NotImplemented
    HelperDict = NotImplemented
    ReadOnlyHelperDictView = NotImplemented

    def __init__(self, *, path_cls: Type[fs.Path], max_parallel_redo_count: int, find_helpers: Optional[bool]):
        if not (isinstance(path_cls, type) and issubclass(path_cls, fs.Path)):
            raise TypeError("'path_cls' must be a subclass of 'dlb.fs.Path'")
        self._path_cls = path_cls
        self._max_parallel_redo_count = max(1, int(max_parallel_redo_count))
        self._find_helpers = None if find_helpers is None else bool(find_helpers)

    @property
    def _active_root_specifics(self):
        return _get_root_specifics()

    @property
    def path_cls(self) -> Type[fs.Path]:
        return self._path_cls

    @property
    def max_parallel_redo_count(self) -> int:
        return self._max_parallel_redo_count

    @property
    def find_helpers(self) -> Optional[bool]:
        return self._find_helpers

    @property
    def root_path(self) -> fs.Path:
        # noinspection PyProtectedMember
        return _get_root_specifics()._root_path

    @property
    def executable_search_paths(self) -> Tuple[fs.Path, ...]:
        # noinspection PyProtectedMember
        return _get_root_specifics()._executable_search_paths

    @property
    def working_tree_time_ns(self) -> int:
        return _get_root_specifics().working_tree_time_ns

    def find_path_in(self, path: fs.PathLike,
                     search_prefixes: Optional[Iterable[fs.PathLike]] = None) -> Optional[fs.Path]:
        # noinspection PyMethodFirstArgAssignment
        self = self._active_root_specifics

        if not isinstance(path, fs.Path):
            path = fs.Path(path)
        if path.is_absolute():
            raise ValueError("'path' must not be absolute")

        if search_prefixes is None:
            prefixes = self._executable_search_paths
        else:
            prefixes = []
            if isinstance(search_prefixes, (str, bytes)):
                raise TypeError("'search_prefixes' must be iterable (other than 'str' or 'bytes')")
            for p in search_prefixes:
                if not isinstance(p, fs.Path):
                    p = fs.Path(p, is_dir=True)
                if not p.is_dir():
                    raise ValueError(f"not a directory: {p.as_string()!r}")
                if not p.is_absolute():
                    p = self._root_path / p
                prefixes.append(p)

        for prefix in prefixes:
            p = prefix / path
            try:
                if path.is_dir() == stat.S_ISDIR(os.stat(p.native).st_mode):
                    return p  # absolute
            except (ValueError, OSError):
                pass

    def working_tree_path_of(self, path: fs.PathLike, *, is_dir: Optional[bool] = None,
                             existing: bool = False, collapsable: bool = False,
                             allow_temporary: bool = False,
                             allow_nontemporary_management: bool = False) -> fs.Path:
        # this must be very fast for relative dlb.fs.Path with existing = True

        # noinspection PyMethodFirstArgAssignment
        self = self._active_root_specifics

        if not isinstance(path, fs.Path) or is_dir is not None and is_dir != path.is_dir():
            path = fs.Path(path, is_dir=is_dir)

        if path.is_absolute():
            # note: do _not_ used path.resolve() or os.path.realpath(), since it would resolve the entire path
            native_components = path.native.components

            # may raise PathNormalizationError
            normalized_native_components = \
                (native_components[0],) + \
                _worktree.normalize_dotdot_native_components(native_components[1:], ref_dir_path=native_components[0])

            native_root_path_components = self._root_path.native.components
            n = len(native_root_path_components)
            if normalized_native_components[:n] != native_root_path_components:
                raise _error.WorkingTreePathError("does not start with the working tree's root path")

            rel_components = ('',) + normalized_native_components[n:]
        else:
            # 'collapsable' means only the part relative to the working tree's root
            ref_dir_path = None if collapsable else self._root_path_native_str
            rel_components = ('',) + _worktree.normalize_dotdot_native_components(
                path.components[1:], ref_dir_path=ref_dir_path)

        if len(rel_components) > 1 and rel_components[1] == _worktree.MANAGEMENTTREE_DIR_NAME:
            if len(rel_components) > 2 and rel_components[2] == _worktree.TEMPORARY_DIR_NAME:
                permitted = allow_temporary
            else:
                permitted = allow_nontemporary_management
            if not permitted:
                msg = f"path in non-permitted part of the working tree: {path.as_string()!r}"
                raise _error.WorkingTreePathError(msg)

        # may raise ValueError
        rel_path = path.__class__(rel_components, is_dir=path.is_dir()) if path.components != rel_components else path

        if not existing:
            try:
                s = str(rel_path.native)
                if s[:2] == '.' + os.path.sep:
                    s = s[2:]
                sr = os.lstat(os.path.sep.join([self._root_path_native_str, s]))
                is_dir = stat.S_ISDIR(sr.st_mode)
            except OSError as e:
                raise _error.WorkingTreePathError(oserror=e) from None
            if is_dir != rel_path.is_dir():
                rel_path = path.__class__(rel_components, is_dir=is_dir)

        return rel_path

    def temporary(self, *, suffix: str = '', is_dir: bool = False) -> _worktree.Temporary:
        # noinspection PyMethodFirstArgAssignment
        self = self._active_root_specifics
        return _worktree.Temporary(path_provider=self._temp_path_provider, suffix=suffix, is_dir=is_dir)

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise AttributeError("public attributes of 'dlb.ex.Context' instances are read-only")
        return super().__setattr__(key, value)


class Context(_BaseContext, metaclass=_ContextMeta):

    # For PyCharm's code completion only.
    # Pitfall: Context().active and Context.active are different.
    active: Optional['Context'] = None

    def __init__(self, *, path_cls: Type[fs.Path] = fs.Path, max_parallel_redo_count: int = 1,
                 find_helpers: Optional[bool] = None):
        super().__init__(path_cls=path_cls, max_parallel_redo_count=max_parallel_redo_count, find_helpers=find_helpers)

        self._env: Optional[_EnvVarDict] = None
        self._helper: Optional[_HelperDict] = None

        self._parent: Optional[Context] = None
        self._optional_redo_sequencer = None  # constructed when needed
        self._root_specifics: Optional[_RootSpecifics] = None

    @property
    def _redo_sequencer(self):
        if self._optional_redo_sequencer is None:
            from . import _aseq
            self._optional_redo_sequencer = _aseq.LimitingResultSequencer()
        return self._optional_redo_sequencer

    def _get_pending_result_proxy_for(self, tool_instance_dbid: Hashable):
        if self._optional_redo_sequencer is None:
            return
        return self._redo_sequencer.get_result_proxy(tool_instance_dbid)

    @property
    def parent(self) -> Optional['Context']:
        return self._parent

    @property
    def env(self) -> _EnvVarDict:
        # noinspection PyStatementEffect
        self._active_root_specifics
        return self._env

    @property
    def helper(self) -> _HelperDict:
        # noinspection PyStatementEffect
        self._active_root_specifics
        return self._helper

    def complete_pending_redos(self):
        if self._optional_redo_sequencer is None:
            return
        # raises RuntimeError if called from redo()
        self._optional_redo_sequencer.complete_all(timeout=None)
        self._consume_redos_and_raise_first_exception()

    def _consume_redos_and_raise_first_exception(self):
        if self._optional_redo_sequencer is None:
            return
        redo_results, redo_exceptions = self._optional_redo_sequencer.consume_all()
        redo_exceptions = [(tid, e) for tid, e in redo_exceptions.items()]
        if redo_exceptions:
            redo_exceptions.sort()
            _, e = redo_exceptions[0]
            raise e

    def summary_of_latest_runs(self, *, max_count: int = 1):
        # noinspection PyMethodFirstArgAssignment
        self = self._active_root_specifics
        return self._rundb.get_latest_successful_run_summaries(max_count)

    def __enter__(self):
        find_helpers = self._find_helpers
        if _contexts:
            if find_helpers is None:
                find_helpers = _contexts[0]._find_helpers
            elif find_helpers and not _contexts[0]._find_helpers:
                raise ValueError("'find_helpers' must be False if 'find_helpers' of root context is False")
            _contexts[-1].complete_pending_redos()
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
            self._parent = _contexts[-1]
            self._env = _EnvVarDict(self, {})
        else:
            self._root_specifics = _RootSpecifics(self._path_cls)
            self._env = _EnvVarDict(self, os.environ)
        if find_helpers is None:
            find_helpers = True

        _contexts.append(self)

        # noinspection PyProtectedMember
        implicit_abs_path_by_helper_path = \
            _contexts[0]._root_specifics._implicit_abs_path_by_helper_path if find_helpers else None
        self._helper = _HelperDict(self, implicit_abs_path_by_helper_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # complete all pending redos (before context is changed in any way)
        try:
            redo_sequencer = self._optional_redo_sequencer
            if redo_sequencer is not None:
                redo_finisher = redo_sequencer.complete_all if exc_val is None else redo_sequencer.cancel_all
                redo_finisher(timeout=None)  # may raise BaseException that is not an Exception (e.g. KeyboardInterrupt)
        finally:
            if not (_contexts and _contexts[-1] == self):
                raise _error.ContextNestingError from None
            _contexts.pop()

            self._parent = None
            self._env = None
            self._helper = None

            if self._root_specifics:
                # noinspection PyProtectedMember
                self._root_specifics._cleanup_and_close(exc_val is None)
                self._root_specifics = None

        if exc_val is None:
            self._consume_redos_and_raise_first_exception()


class ReadOnlyContext(_BaseContext):
    # Must only be used while a root context exists

    def __init__(self, context: Context):
        if not isinstance(context, Context):
            raise TypeError("'context' must be a Context object")
        _get_root_specifics()
        super().__init__(path_cls=context.path_cls, max_parallel_redo_count=context.max_parallel_redo_count,
                         find_helpers=context.find_helpers)
        self._env = _ReadOnlyEnvVarDictView(context.env)
        self._helper = _ReadOnlyHelperDictView(context.helper)

    @property
    def env(self) -> _ReadOnlyEnvVarDictView:
        return self._env

    @property
    def helper(self) -> _ReadOnlyHelperDictView:
        return self._helper


ut.set_module_name_to_parent_by_name(vars(), __all__)
