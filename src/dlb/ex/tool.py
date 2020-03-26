# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Dependency-aware tool execution."""

__all__ = (
    'Tool',
    'DefinitionAmbiguityError',
    'DependencyError',
    'ExecutionParameterError',
    'RedoError',
    'HelperExecutionError',
    'is_complete'
)

import sys
import re
import os
import collections
import hashlib
import inspect
from typing import Type, Optional, Any, Dict, Tuple, Set, Iterable, Collection
from .. import ut
from .. import fs
from .. import cf
from .. import di
from . import rundb
from . import worktree
from . import context as context_
from . import depend
from . import dependaction
assert sys.version_info >= (3, 7)


UPPERCASE_WORD_NAME_REGEX = re.compile('^[A-Z][A-Z0-9]*(_[A-Z][A-Z0-9]*)*$')
assert UPPERCASE_WORD_NAME_REGEX.match('A')
assert UPPERCASE_WORD_NAME_REGEX.match('A2_B')
assert not UPPERCASE_WORD_NAME_REGEX.match('_A')

LOWERCASE_WORD_NAME_REGEX = re.compile('^[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$')
assert LOWERCASE_WORD_NAME_REGEX.match('object_file')
assert not LOWERCASE_WORD_NAME_REGEX.match('_object_file_')
assert not LOWERCASE_WORD_NAME_REGEX.match('Object_file_')


# key: (source_path, in_archive_path, lineno), value: class with metaclass _ToolMeta
_tool_class_by_definition_location = {}

# key: dlb.ex.Tool, value: ToolInfo
_registered_info_by_tool = {}


class DefinitionAmbiguityError(SyntaxError):
    pass


class DependencyError(ValueError):
    pass


class ExecutionParameterError(Exception):
    pass


class RedoError(Exception):
    pass


class HelperExecutionError(Exception):
    pass


ToolInfo = collections.namedtuple('ToolInfo', ('permanent_local_tool_id', 'definition_paths'))


class _RedoContext(context_.ReadOnlyContext):

    def __init__(self, context: context_.Context, dependency_action_by_path: Dict[fs.Path, dependaction.Action]):
        if not isinstance(dependency_action_by_path, dict):
            raise TypeError

        super().__init__(context)
        self._dependency_action_by_path = dependency_action_by_path
        self._unchanged_paths = set()

    async def execute_helper(self, helper_file: fs.PathLike, arguments: Iterable[Any] = (), *,
                             cwd: Optional[fs.PathLike] = None, expected_returncodes: Collection[int] = frozenset([0]),
                             forced_env: Optional[Dict[str, str]] = None,
                             stdin=None, stdout=None, stderr=None, limit: int = 2**16):
        if not isinstance(helper_file, fs.Path):
            helper_file = fs.Path(helper_file)

        cwd = fs.Path('.') if cwd is None else self.working_tree_path_of(cwd, is_dir=True, allow_temporary=True)
        longest_dotdot_prefix = ()

        if helper_file.is_dir():
            raise ValueError(f"cannot execute directory: {helper_file.as_string()!r}")

        helper_file_path = self.helper[helper_file]
        commandline_tokens = [str(helper_file_path.native)]
        for a in arguments:
            if isinstance(a, fs.Path):
                if not a.is_absolute():
                    a = self.working_tree_path_of(a, existing=True,
                                                  allow_temporary=True).relative_to(cwd, collapsable=True)
                    c = a.components[1:]
                    if c[:len(longest_dotdot_prefix)] == longest_dotdot_prefix:
                        while len(longest_dotdot_prefix) < len(c) and c[len(longest_dotdot_prefix)] == '..':
                            longest_dotdot_prefix += ('..',)
                a = a.native
            commandline_tokens.append(str(a))

        if longest_dotdot_prefix:
            worktree.normalize_dotdot_native_components(cwd.components[1:] + longest_dotdot_prefix,
                                                        ref_dir_path=str(self.root_path.native))

        if forced_env is None:
            forced_env = {}
        env = {k: v for k, v in self.env.items()}
        env.update(forced_env)

        if di.is_unsuppressed_level(cf.level.HELPER_EXECUTION):
            argument_list_str = ', '.join([repr(t) for t in commandline_tokens[1:]])
            env_str = repr(env)
            msg = (
                f'execute helper {helper_file.as_string()!r}\n'
                f'    path: \t{helper_file_path.as_string()!r}\n'
                f'    arguments: \t{argument_list_str}\n'
                f'    directory: \t{cwd.as_string()!r}\n'
                f'    environment: \t{env_str}'
            )
            di.inform(msg, level=cf.level.HELPER_EXECUTION)

        import asyncio
        proc = await asyncio.create_subprocess_exec(
            *commandline_tokens,  # must all by str
            cwd=(self.root_path / cwd).native, env=env,
            stdin=stdin, stdout=stdout, stderr=stderr, limit=limit)
        stdout, stderr = await proc.communicate()
        returncode = proc.returncode

        if returncode not in expected_returncodes:
            msg = f"execution of {helper_file.as_string()!r} returned unexpected exit code {proc.returncode}"
            raise HelperExecutionError(msg)

        return returncode, stdout, stderr

    def replace_output(self, path: fs.PathLike, source: fs.PathLike):
        # *path* may or may not exist.
        #
        # After if successful completion
        #  - *path* exists
        #  - *source* does not exist

        if not isinstance(path, fs.Path):
            path = fs.Path(path)
        if not isinstance(source, fs.Path):
            source = fs.Path(source)

        action = self._dependency_action_by_path.get(path)
        if action is None:
            msg = f"path is not contained in any explicit output dependency: {path.as_string()!r}"
            raise ValueError(msg)

        if path.is_dir() != source.is_dir():
            if path.is_dir():
                msg = f"cannot replace directory by non-directory: {path.as_string()!r}"
            else:
                msg = f"cannot replace non-directory by directory: {path.as_string()!r}"
            raise ValueError(msg)

        try:
            source = self.working_tree_path_of(source, allow_temporary=True)
        except worktree.WorkingTreePathError as e:
            if e.oserror is not None:
                e = e.oserror
            msg = (
                f"'source' is not a permitted working tree path of an existing filesystem object: "
                f"{source.as_string()!r}\n"
                f"  | reason: {ut.exception_to_line(e)}"
            )
            raise ValueError(msg)

        if path == source:
            raise ValueError(f"cannot replace a path by itself: {path.as_string()!r}")

        output_possibly_changed = action.replace_filesystem_object(destination=path, source=source, context=self)
        if output_possibly_changed:
            self._unchanged_paths.discard(path)
        else:
            self._unchanged_paths.add(path)

    @property
    def modified_outputs(self) -> Set[fs.Path]:
        return set(self._dependency_action_by_path) - self._unchanged_paths


_RedoContext.__name__ = 'RedoContext'
_RedoContext.__qualname__ = 'Tool.RedoContext'
ut.set_module_name_to_parent(_RedoContext)


def _get_memo_for_fs_input_dependency_from_rundb(encoded_path: str, last_encoded_memo: Optional[bytes],
                                                 needs_redo: bool, root_path: fs.Path) \
        -> Tuple[rundb.FilesystemObjectMemo, bool]:

    path = None
    memo = rundb.FilesystemObjectMemo()

    try:
        path = rundb.decode_encoded_path(encoded_path)  # may raise ValueError
    except ValueError:
        if not needs_redo:
            di.inform(f"redo necessary because of invalid encoded path: {encoded_path!r}",
                      level=cf.level.REDO_SUSPICIOUS_REASON)
            needs_redo = True

    if path is None:
        return memo, needs_redo

    try:
        # do _not_ check if in managed tree: does no harm if _not_ in managed tree
        # may raise OSError or ValueError (if 'path' not representable on native system)
        memo = worktree.read_filesystem_object_memo(root_path / path)
    except (ValueError, FileNotFoundError):
        # ignore if did not exist according to valid 'encoded_memo'
        did_not_exist_before_last_redo = False
        try:
            did_not_exist_before_last_redo = \
                last_encoded_memo is None or rundb.decode_encoded_fsobject_memo(last_encoded_memo).stat is None
        except ValueError:
            pass
        if not did_not_exist_before_last_redo:
            if not needs_redo:
                msg = f"redo necessary because of non-existent filesystem object: {path.as_string()!r}"
                di.inform(msg, level=cf.level.REDO_REASON)
                needs_redo = True
    except OSError:
        # comparision not possible -> redo
        if not needs_redo:
            msg = f"redo necessary because of inaccessible filesystem object: {path.as_string()!r}"
            di.inform(msg, level=cf.level.REDO_REASON)
            needs_redo = True  # comparision not possible -> redo

    return memo, needs_redo  # memo.state may be None


def _check_and_memorize_explicit_fs_input_dependencies(tool, dependency_actions: Tuple[dependaction.Action, ...],
                                                       context: context_.Context) \
        -> Dict[str, rundb.FilesystemObjectMemo]:

    # For all explicit input dependencies of *tool* in *dependency_actions* for filesystem objects:
    # Checks existence, reads and checks its FilesystemObjectMemo.
    #
    # Treats all definitions file of this tool class that are in the managed tree as explicit input dependencies.
    #
    # Returns a dictionary whose key are encoded managed tree paths and whose values are the corresponding
    # FilesystemObjectMemo m with ``m.stat is not None``.

    memo_by_encoded_path: Dict[str, rundb.FilesystemObjectMemo] = {}

    for action in dependency_actions:
        # read memo of each filesystem object of a explicit input dependency in a repeatable order
        if action.dependency.explicit and isinstance(action.dependency, depend.Input) \
                and action.dependency.Value is fs.Path:
            validated_value_tuple = action.dependency.tuple_from_value(getattr(tool, action.name))
            for p in validated_value_tuple:  # p is a dlb.fs.Path
                try:
                    try:
                        p = context.working_tree_path_of(p, existing=True, collapsable=False)
                    except ValueError as e:
                        if isinstance(e, worktree.WorkingTreePathError) and e.oserror is not None:
                            raise e.oserror
                        if not p.is_absolute():
                            raise ValueError('not a managed tree path') from None
                        # absolute paths to the management tree are ok

                    # p is a relative path of a filesystem object in the managed tree or an absolute path
                    # of filesystem object outside the managed tree
                    if not p.is_absolute():
                        encoded_path = rundb.encode_path(p)
                        memo = memo_by_encoded_path.get(encoded_path)
                        if memo is None:
                            memo = worktree.read_filesystem_object_memo(context.root_path / p)  # may raise OSError
                        action.check_filesystem_object_memo(memo)  # raise ValueError if memo is not as expected
                        memo_by_encoded_path[encoded_path] = memo
                        assert memo.stat is not None
                except ValueError as e:
                    msg = (
                        f"input dependency {action.name!r} contains an invalid path: {p.as_string()!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise DependencyError(msg) from None
                except FileNotFoundError:
                    msg = (
                        f"input dependency {action.name!r} contains a path of a "
                        f"non-existent filesystem object: {p.as_string()!r}"
                    )
                    raise DependencyError(msg) from None
                except OSError as e:
                    msg = (
                        f"input dependency {action.name!r} contains a path of an "
                        f"inaccessible filesystem object: {p.as_string()!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise DependencyError(msg) from None

    # treat all files used for definition of self.__class__ like explicit input dependencies if they
    # have a managed tree path.
    definition_file_count = 0
    for pn in get_and_register_tool_info(tool.__class__).definition_paths:
        try:
            p = context.working_tree_path_of(fs.Path.Native(pn), existing=True, collapsable=False)
            encoded_path = rundb.encode_path(p)
            memo = memo_by_encoded_path.get(encoded_path)
            if memo is None:
                memo = worktree.read_filesystem_object_memo(context.root_path / p)  # may raise OSError
            assert memo.stat is not None
            definition_file_count += 1
            memo_by_encoded_path[encoded_path] = memo
            assert memo.stat is not None
        except (ValueError, OSError):
            # silently ignore all definition files not in managed tree
            pass
    di.inform(f"added {definition_file_count} tool definition files as input dependency",
              level=cf.level.REDO_NECESSITY_CHECK)

    return memo_by_encoded_path


def _check_explicit_fs_output_dependencies(tool, dependency_actions: Tuple[dependaction.Action, ...],
                                           encoded_paths_of_explicit_input_dependencies: Set[str],
                                           needs_redo: bool,
                                           context: context_.Context) \
        -> Tuple[Dict[fs.Path, dependaction.Action], Set[fs.Path], bool]:
    # For all explicit output dependencies of *tool* in *dependency_actions* for filesystem objects:
    # Checks existence, reads and checks its FilesystemObjectMemo.
    #
    # Returns ``True`` if at least one of the filesystem objects does not exist.

    dependency_action_by_encoded_path = {}
    dependency_action_by_path = {}

    # managed tree paths of existing filesystem objects with unexpected memos (e.g. wrong type):
    obstructive_paths = set()

    for action in dependency_actions:

        # read memo of each filesystem object of a explicit input dependency in a repeatable order
        if action.dependency.explicit and isinstance(action.dependency, depend.Output) and \
                action.dependency.Value is fs.Path:

            validated_value_tuple = action.dependency.tuple_from_value(getattr(tool, action.name))
            for p in validated_value_tuple:  # p is a dlb.fs.Path
                try:
                    p = context.working_tree_path_of(p, existing=True, collapsable=True)
                except ValueError as e:
                    msg = (
                        f"output dependency {action.name!r} contains a path that is not a managed tree path: "
                        f"{p.as_string()!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise DependencyError(msg) from None
                encoded_path = rundb.encode_path(p)
                if encoded_path in encoded_paths_of_explicit_input_dependencies:
                    msg = (
                        f"output dependency {action.name!r} contains a path that is also an explicit "
                        f"input dependency: {p.as_string()!r}"
                    )
                    raise DependencyError(msg)
                a = dependency_action_by_encoded_path.get(encoded_path)
                if a is not None:
                    msg = (
                        f"output dependencies {action.name!r} and {a.name!r} both contain the same path: "
                        f"{p.as_string()!r}"
                    )
                    raise DependencyError(msg)
                dependency_action_by_encoded_path[encoded_path] = action
                dependency_action_by_path[p] = action
                memo = None
                try:
                    # may raise OSError or ValueError (if 'path' not representable on native system)
                    memo = worktree.read_filesystem_object_memo(context.root_path / p)
                    action.check_filesystem_object_memo(memo)  # raise ValueError if memo is not as expected
                except (ValueError, OSError) as e:
                    if memo is not None and memo.stat is not None:
                        obstructive_paths.add(p)
                    if not needs_redo:
                        msg = (
                            f"redo necessary because of filesystem object that "
                            f"is an output dependency: {p.as_string()!r}\n"
                            f"    reason: {ut.exception_to_line(e)}"
                        )
                        di.inform(msg, level=cf.level.REDO_REASON)
                        needs_redo = True

    return dependency_action_by_path, obstructive_paths, needs_redo


def _check_envvar_dependencies(tool, dependency_actions: Tuple[dependaction.Action, ...], context: context_.Context):
    envvar_value_by_name = {}
    action_by_envvar_name = {}

    for action in dependency_actions:
        d = action.dependency
        if d.Value is depend.EnvVarInput.Value:
            a = action_by_envvar_name.get(d.name)
            if a is not None:
                msg = (
                    f"input dependencies {action.name!r} and {a.name!r} both define the same "
                    f"environment variable: {d.name!r}"
                )
                raise DependencyError(msg)
            if action.dependency.explicit:
                for ev in action.dependency.tuple_from_value(getattr(tool, action.name)):
                    envvar_value_by_name[ev.name] = ev.raw  # ev is a depend.EnvVarInput.Value
            else:
                value = envvar_value_by_name.get(d.name)
                if value is None:
                    if d.required:
                        try:
                            value = context.env[d.name]
                        except KeyError as e:
                            raise RedoError(*e.args) from None
                    else:
                        value = context.env.get(d.name)
                if value is not None:
                    envvar_value_by_name[d.name] = value  # validate at redo
            action_by_envvar_name[d.name] = action

    envvar_digest = b''
    for name in sorted(envvar_value_by_name):
        envvar_digest += ut.to_permanent_local_bytes((name, envvar_value_by_name[name]))
    if len(envvar_digest) >= 20:
        envvar_digest = hashlib.sha1(envvar_digest).digest()

    return envvar_value_by_name, envvar_digest


class _RunResult:
    # Attribute represent concrete dependencies of a tool instance.
    # Explicit dependencies are referred to the tool instance.
    # Non-explicit dependencies can be set exactly once, if *redo* is True.
    #
    # To be used by run() and redo().

    def __init__(self, tool, redo: bool):
        super().__setattr__('_tool', tool)
        super().__setattr__('_redo', bool(redo))

    def __setattr__(self, key, value):
        if not self._redo:
            raise AttributeError

        try:
            role = getattr(self._tool.__class__, key)
            if not isinstance(role, depend.Dependency):
                raise AttributeError
        except AttributeError:
            raise AttributeError(f"{key!r} is not a dependency")

        if key in self.__dict__:
            raise AttributeError(f"{key!r} is already assigned")

        if role.explicit:
            raise AttributeError(f"{key!r} is not a non-explicit dependency")

        if value is not None:
            validated_value = role.validate(value)
        elif not role.required:
            validated_value = None
        else:
            raise ValueError('value for required dependency must not be None')

        super().__setattr__(key, validated_value)

    def __getattr__(self, item):
        try:
            role = getattr(self._tool.__class__, item)
            if not isinstance(role, depend.Dependency):
                raise AttributeError
        except AttributeError:
            raise AttributeError(f"{item!r} is not a dependency")

        if role.explicit:
            return getattr(self._tool, item)

        return NotImplemented

    def __bool__(self) -> bool:
        return self._redo

    def __repr__(self) -> str:
        # noinspection PyProtectedMember
        dependencies = [(n, getattr(self, n)) for n in self._tool.__class__._dependency_names]
        args = ', '.join('{}={}'.format(k, repr(v)) for k, v in dependencies if v is not NotImplemented)
        return f"{self.__class__.__name__}({args})"


_RunResult.__name__ = 'RunResult'
_RunResult.__qualname__ = 'Tool.{}'.format(_RunResult.__name__)


# noinspection PyProtectedMember,PyUnresolvedReferences
class _ToolBase:
    # only _ToolBase should construct instances of this:
    RedoContext = NotImplemented

    def __init__(self, **kwargs):
        super().__init__()

        # replace all dependency roles by concrete dependencies or None or NotImplemented

        # order is important:
        dependency_names = self.__class__._dependency_names   # type: typing.Tuple[str, ...]
        dependency_names_set = set(dependency_names)

        names_of_assigned = set()
        for name, value in kwargs.items():
            if name not in dependency_names_set:
                names = ', '.join(repr(n) for n in dependency_names)
                msg = (
                    f"keyword argument does not name a dependency role of {self.__class__.__qualname__!r}: {name!r}\n"
                    f"  | dependency roles: {names}"
                )
                raise DependencyError(msg)

            role = getattr(self.__class__, name)
            if not role.explicit:
                msg = (
                    f"keyword argument does name a non-explicit dependency role: {name!r}\n"
                    f"  | non-explicit dependency must not be assigned at construction"
                )
                raise DependencyError(msg)

            if value is None:
                validated_value = None
                if role.required:
                    msg = f"keyword argument for required dependency role must not be None: {name!r}"
                    raise DependencyError(msg)
            else:
                try:
                    validated_value = role.validate(value)
                except (TypeError, ValueError) as e:
                    msg = (
                        f"keyword argument for dependency role {name!r} is invalid: {value!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise DependencyError(msg)

            object.__setattr__(self, name, validated_value)
            names_of_assigned.add(name)

        # build permanent fingerprint for tool instance from all explicit dependencies

        hashalg = hashlib.sha1()
        # SHA1 is always present and fasted according to this:
        # http://atodorov.org/blog/2013/02/05/performance-test-md5-sha1-sha256-sha512/

        names_of_notassigned = dependency_names_set - names_of_assigned
        for name in dependency_names:  # order is important
            role = getattr(self.__class__, name)
            if name in names_of_notassigned:
                if role.explicit:
                    if role.required:
                        msg = f"missing keyword argument for required and explicit dependency role: {name!r}"
                        raise DependencyError(msg)
                    object.__setattr__(self, name, None)
                else:
                    object.__setattr__(self, name, NotImplemented)
            if role.explicit:
                # this remains unchanged between dlb run if dlb.ex.platform.PERMANENT_PLATFORM_ID remains unchanged
                try:
                    action = dependaction.get_action(role, name)
                    dependency_fingerprint = action.get_permanent_local_instance_id()

                    validated_values = role.tuple_from_value(getattr(self, name))
                    dependency_fingerprint += action.get_permanent_local_value_id(validated_values)

                    # since 'dependency_names' and 'r.explicit of all their members r are fixed for all instances
                    # of this class, the order of dependency roles is sufficient for their identification
                    hashalg.update(dependency_fingerprint)  # dependency_fingerprint must not be empty
                except KeyError:
                    msg = f"keyword names unregistered dependency class {role.__class__!r}: {name!r}"
                    raise DependencyError(msg)

        # permanent local tool instance fingerprint for this instance (do not compare fingerprint between
        # different self.__class__!)
        object.__setattr__(self, 'fingerprint', hashalg.digest())  # always 20 byte

    # final
    def run(self, *, force_redo: bool = False):
        with di.Cluster('prepare tool instance', level=cf.level.RUN_PREPARATION, with_time=True, is_progress=True):
            # noinspection PyTypeChecker
            context: context_.Context = context_.Context.active

            dependency_actions = tuple(
                dependaction.get_action(getattr(self.__class__, n), n)
                for n in self.__class__._dependency_names
            )

            execution_parameter_digest = b''
            for name in self.__class__._execution_parameter_names:
                value = getattr(self.__class__, name)
                try:
                    execution_parameter_digest += ut.to_permanent_local_bytes(value)
                except TypeError:
                    fundamentals = ', '.join(repr(c.__name__) for c in ut.non_container_fundamental_types)
                    msg = (
                        f"value of execution parameter {name!r} is not fundamental: {value!r}\n"
                        f"  | an object is fundamental if it is None, or of type {fundamentals}, "
                        f"or a mapping or iterable of only such objects"
                    )
                    raise ExecutionParameterError(msg) from None
            if len(execution_parameter_digest) >= 20:
                execution_parameter_digest = hashlib.sha1(execution_parameter_digest).digest()

            db = context_._get_rundb()

            tool_instance_dbid = db.get_and_register_tool_instance_dbid(
                get_and_register_tool_info(self.__class__).permanent_local_tool_id,
                self.fingerprint)
            di.inform(f"tool instance is {tool_instance_dbid!r}", level=cf.level.RUN_PREPARATION)

            result_proxy_of_last_run = context._get_pending_result_proxy_for(tool_instance_dbid)
            if result_proxy_of_last_run is not None:
                with di.Cluster('wait for last redo to complete', level=cf.level.RUN_SERIALIZATION,
                                with_time=True, is_progress=True):
                    with result_proxy_of_last_run:
                        pass

        with di.Cluster(f'check redo necessity for tool instance {tool_instance_dbid!r}',
                        level=cf.level.REDO_NECESSITY_CHECK, with_time=True, is_progress=True):

            with di.Cluster('explicit input dependencies', level=cf.level.REDO_NECESSITY_CHECK,
                            with_time=True, is_progress=True):
                memo_by_encoded_path = \
                    _check_and_memorize_explicit_fs_input_dependencies(self, dependency_actions, context)

            # 'memo_by_encoded_path' contains a current memo for every filesystem object in the managed tree that
            # is an explicit input dependency of this call of 'run()' or an non-explicit input dependency of the
            # last successful redo of the same tool instance according to the run-database

            with di.Cluster('explicit output dependencies', level=cf.level.REDO_NECESSITY_CHECK,
                            with_time=True, is_progress=True):
                encoded_paths_of_explicit_input_dependencies = set(memo_by_encoded_path.keys())
                dependency_action_by_path, obstructive_paths, needs_redo = _check_explicit_fs_output_dependencies(
                    self, dependency_actions, encoded_paths_of_explicit_input_dependencies, False, context)

            with di.Cluster('input dependencies of the last redo', level=cf.level.REDO_NECESSITY_CHECK,
                            with_time=True, is_progress=True):
                db = context_._get_rundb()
                inputs_from_last_redo = db.get_fsobject_inputs(tool_instance_dbid)
                for encoded_path, (is_explicit, last_encoded_memo) in inputs_from_last_redo.items():
                    if not is_explicit and encoded_path not in memo_by_encoded_path:
                        memo, needs_redo = _get_memo_for_fs_input_dependency_from_rundb(
                            encoded_path, last_encoded_memo, needs_redo, context.root_path)
                        memo_by_encoded_path[encoded_path] = memo  # memo.state may be None

            # 'memo_by_encoded_path' contains a current memo for every filesystem object in the managed tree that
            # is an explicit or non-explicit input dependency of this call of 'run()' or an non-explicit input
            # dependency of the last successful redo of the same tool instance according to the run-database

            with di.Cluster('environment variables', level=cf.level.REDO_NECESSITY_CHECK,
                            with_time=True, is_progress=True):
                envvar_value_by_name, envvar_digest = _check_envvar_dependencies(self, dependency_actions, context)

            if not needs_redo and force_redo:
                di.inform("redo requested by run()", level=cf.level.REDO_REASON)
                needs_redo = True

            if not needs_redo:
                domain_inputs_in_db = db.get_domain_inputs(tool_instance_dbid)
                redo_request_in_db = domain_inputs_in_db.get(rundb.Domain.REDO_REQUEST.value)
                redo_request_in_db = None if redo_request_in_db is None else bool(redo_request_in_db)

                execution_parameter_digest_in_db = domain_inputs_in_db.get(rundb.Domain.EXECUTION_PARAMETERS.value)
                envvar_digest_in_db = domain_inputs_in_db.get(rundb.Domain.ENVIRONMENT_VARIABLES.value)
                if redo_request_in_db is True:
                    di.inform("redo requested by last successful redo", level=cf.level.REDO_REASON)
                    needs_redo = True
                elif execution_parameter_digest != execution_parameter_digest_in_db:
                    di.inform("redo necessary because of changed execution parameter", level=cf.level.REDO_REASON)
                    needs_redo = True
                elif envvar_digest != envvar_digest_in_db:
                    di.inform("redo necessary because of changed environment variable", level=cf.level.REDO_REASON)
                    needs_redo = True

            if not needs_redo:
                with di.Cluster('compare input dependencies with state before last successful redo',
                                level=cf.level.REDO_NECESSITY_CHECK, with_time=True, is_progress=True):
                    # sorting not necessary for repeatability
                    for encoded_path, memo in memo_by_encoded_path.items():
                        is_explicit, last_encoded_memo = inputs_from_last_redo.get(encoded_path, (True, None))
                        assert memo.stat is not None or not is_explicit
                        redo_reason = rundb.compare_fsobject_memo_to_encoded_from_last_redo(
                            memo, last_encoded_memo, encoded_path in encoded_paths_of_explicit_input_dependencies)
                        if redo_reason is not None:
                            path = rundb.decode_encoded_path(encoded_path)
                            msg = (
                                f"redo necessary because of filesystem object: {path.as_string()!r}\n"
                                f"    reason: {redo_reason}"
                            )
                            di.inform(msg, level=cf.level.REDO_REASON)
                            needs_redo = True
                            break

        if not needs_redo:
            context_._register_successful_run(False)
            return _RunResult(self, False)  # no redo

        if obstructive_paths:
            with di.Cluster('remove obstructive filesystem objects that are explicit output dependencies',
                            level=cf.level.REDO_PREPARATION, with_time=True, is_progress=True):
                with context.temporary(is_dir=True) as tmp_dir:
                    for p in obstructive_paths:
                        worktree.remove_filesystem_object(context.root_path / p, abs_empty_dir_path=tmp_dir,
                                                          ignore_non_existent=True)

        result = _RunResult(self, True)
        for action in dependency_actions:
            if not action.dependency.explicit and action.dependency.Value is depend.EnvVarInput.Value:
                try:
                    value = envvar_value_by_name.get(action.dependency.name)
                    setattr(result, action.name, value)  # validates on assignment
                except (TypeError, ValueError) as e:
                    msg = (
                        f"input dependency {action.name!r} cannot use environment variable {action.dependency.name!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise RedoError(msg) from None

        # note: no db.commit() necessary as long as root context does commit on exception
        redo_sequencer = context._redo_sequencer
        tid = redo_sequencer.wait_then_start(
            context.max_parallel_redo_count, None, self._redo_with_aftermath,
            result=result, context=_RedoContext(context, dependency_action_by_path),
            dependency_actions=dependency_actions, memo_by_encoded_path=memo_by_encoded_path,
            encoded_paths_of_explicit_input_dependencies=encoded_paths_of_explicit_input_dependencies,
            execution_parameter_digest=execution_parameter_digest, envvar_digest=envvar_digest,
            db=db, tool_instance_dbid=tool_instance_dbid)

        return redo_sequencer.create_result_proxy(tid, uid=tool_instance_dbid, expected_class=_RunResult)

    async def _redo_with_aftermath(self, result, context,
                                   dependency_actions, memo_by_encoded_path,
                                   encoded_paths_of_explicit_input_dependencies,
                                   execution_parameter_digest, envvar_digest,
                                   db, tool_instance_dbid):
        # note: no db.commit() necessary as long as root context does commit on exception
        di.inform(f"start redo for tool instance {tool_instance_dbid!r}", level=cf.level.REDO_START, with_time=True)
        redo_request = bool(await self.redo(result, context))

        with di.Cluster(f"memorize successful redo for tool instance {tool_instance_dbid!r}",
                        level=cf.level.REDO_AFTERMATH, with_time=True):
            # collect non-explicit input and output dependencies of this redo
            encoded_paths_of_nonexplicit_input_dependencies = set()
            encoded_paths_of_modified_output_dependencies = set()

            for action in dependency_actions:
                if not action.dependency.explicit:
                    validated_value = getattr(result, action.name)
                    if validated_value is NotImplemented:
                        if action.dependency.required:
                            msg = (
                                f"non-explicit dependency not assigned during redo: {action.name!r}\n"
                                f"  | use 'result.{action.name} = ...' in body of redo(self, result, context)"
                            )
                            raise RedoError(msg)
                        validated_value = None
                        setattr(result, action.name, validated_value)
                    if action.dependency.Value is fs.Path:
                        if isinstance(action.dependency, depend.Input):
                            paths = action.dependency.tuple_from_value(validated_value)
                            for p in paths:
                                try:
                                    p = context.working_tree_path_of(p, existing=True, collapsable=False)
                                except ValueError:
                                    if not p.is_absolute():
                                        msg = (
                                            f"non-explicit input dependency {action.name!r} contains a relative path "
                                            f"that is not a managed tree path: {p.as_string()!r}"
                                        )
                                        raise RedoError(msg) from None
                                # absolute paths to the management tree are silently ignored
                                if not p.is_absolute():
                                    encoded_paths_of_nonexplicit_input_dependencies.add(rundb.encode_path(p))
                        elif isinstance(action.dependency, depend.Output):
                            paths = action.dependency.tuple_from_value(validated_value)
                            for p in paths:
                                try:
                                    p = context.working_tree_path_of(p, existing=True, collapsable=False)
                                except ValueError:
                                    msg = (
                                        f"non-explicit output dependency {action.name!r} contains a path "
                                        f"that is not a managed tree path: {p.as_string()!r}"
                                    )
                                    raise RedoError(msg) from None
                                encoded_paths_of_modified_output_dependencies.add(rundb.encode_path(p))

            encoded_paths_of_input_dependencies = \
                encoded_paths_of_explicit_input_dependencies | encoded_paths_of_nonexplicit_input_dependencies
            for p in context.modified_outputs:
                encoded_paths_of_modified_output_dependencies.add(rundb.encode_path(p))

            with di.Cluster('store state before redo in run-database', level=cf.level.REDO_AFTERMATH):
                # redo was successful, so save the state before the redo to the run-database
                info_by_fsobject_dbid = {
                    encoded_path: (
                        encoded_path in encoded_paths_of_explicit_input_dependencies,
                        rundb.encode_fsobject_memo(memo))
                    for encoded_path, memo in memo_by_encoded_path.items()
                    if encoded_path in encoded_paths_of_input_dependencies  # drop obsolete non-explicit dependencies
                }
                info_by_fsobject_dbid.update({  # add new non-explicit dependencies
                    encoded_path: (False, None)
                    for encoded_path in encoded_paths_of_nonexplicit_input_dependencies - set(info_by_fsobject_dbid)
                })

                db.update_dependencies(
                    tool_instance_dbid,
                    info_by_encoded_path=info_by_fsobject_dbid,
                    memo_digest_by_domain={
                        rundb.Domain.REDO_REQUEST.value: b'\x01' if redo_request else None,
                        rundb.Domain.EXECUTION_PARAMETERS.value: execution_parameter_digest,
                        rundb.Domain.ENVIRONMENT_VARIABLES.value: envvar_digest
                    },
                    encoded_paths_of_modified=encoded_paths_of_modified_output_dependencies)

            # note: no db.commit() necessary as long as root context does commit on exception

        context_._register_successful_run(True)

        return result

    async def redo(self, result: _RunResult, context: _RedoContext) -> Optional[bool]:
        raise NotImplementedError

    def __setattr__(self, name: str, value):
        raise AttributeError

    def __delattr__(self, name: str):
        raise AttributeError

    def __repr__(self):
        dependency_tokens = [
            '{}={!r}'.format(n, getattr(self, n))
            for n in self.__class__._dependency_names
        ]
        return '{}({})'.format(self.__class__.__qualname__, ', '.join(dependency_tokens))


# noinspection PyProtectedMember
depend._inject_into(_ToolBase, 'Tool', '.'.join(_ToolBase.__module__.split('.')[:-1]))


class _ToolMeta(type):

    OVERRIDEABLE_ATTRIBUTES = frozenset(('redo', '__doc__', '__module__', '__annotations__'))

    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)

        # prevent attributes of _ToolBase from being overridden
        protected_attrs = (set(_ToolBase.__dict__.keys()) - _ToolMeta.OVERRIDEABLE_ATTRIBUTES | {'__new__'})
        attrs = set(cls.__dict__) & protected_attrs
        if attrs:
            raise AttributeError("must not be overridden in a 'dlb.ex.Tool': {}".format(repr(sorted(attrs)[0])))
        cls.check_own_attributes()
        dependency_names, execution_parameter_names = cls._get_names()

        super().__setattr__('_dependency_names', dependency_names)
        super().__setattr__('_execution_parameter_names', execution_parameter_names)
        frame_info = inspect.getframeinfo(inspect.currentframe().f_back, context=0)
        location = cls._find_definition_location(frame_info)
        super().__setattr__('definition_location', location)
        _tool_class_by_definition_location[location] = cls

    def _find_definition_location(cls, defining_frame) -> Tuple[str, Optional[str], int]:
        # Return the location, cls is defined.
        # Raises DefinitionAmbiguityError, if the location is unknown or already a class with the same metaclass
        # was defined at the same location (abspath of an existing source file and line number).
        # If the source file is a zip archive with a filename ending in '.zip', the path relative to the root
        # of the archive is also given.

        # frame relies based on best practises, correct information not guaranteed
        source_lineno = defining_frame.lineno
        source_path = defining_frame.filename
        if not os.path.isabs(source_path):
            msg = (
                f"invalid tool definition: location of definition depends on current working directory\n"
                f"  | class: {cls!r}\n"
                f"  | source file: {defining_frame.filename!r}\n"
                f"  | make sure the matching module search path is an absolute path when the "
                f"defining module is imported"
            )
            raise DefinitionAmbiguityError(msg)

        try:
            in_archive_path = None
            if not os.path.isfile(source_path):
                # zipimport:
                #     https://www.python.org/dev/peps/pep-0273/:
                #         "only files *.py and *.py[co] are available for import"
                #
                #     The source file path of an object imported from a zip archive has the relative path inside the
                #     archive appended to the path of the zip file (e.g. 'x.zip/y/z.py').
                #     A module name must be a Python identifier, so it must not contain a '.'.
                #     Therefore, the file path of the archive can always be determined unambiguously if the
                #     archive's filename contains a '.'.
                if os.path.altsep:
                    source_path = source_path.replace(os.path.altsep, os.path.sep)

                ext = '.zip'

                # TypeError on assignment if no match:
                source_path, in_archive_path = source_path.rstrip(os.path.sep).rsplit(ext + os.path.sep)
                source_path += ext

                if not os.path.isfile(source_path):
                    raise ValueError
                in_archive_path = os.path.normpath(in_archive_path)

        except Exception:
            msg = (
                f"invalid tool definition: location of definition is unknown\n"
                f"  | class: {cls!r}\n"
                f"  | define the class in a regular file or in a zip archive ending in '.zip'\n"
                f"  | note also the significance of upper and lower case of module search paths on "
                f"case-insensitive filesystems"
            )
            raise DefinitionAmbiguityError(msg) from None

        location = source_path, in_archive_path, source_lineno
        existing_location = _tool_class_by_definition_location.get(location)
        if existing_location is not None:
            msg = (
                f"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
                f"  | location: {source_path!r}:{source_lineno}\n"
                f"  | class: {existing_location!r}"
            )
            raise DefinitionAmbiguityError(msg)

        return location

    def check_own_attributes(cls):
        for name, value in cls.__dict__.items():
            defining_base_classes = tuple(c for c in cls.__bases__ if name in c.__dict__)
            if UPPERCASE_WORD_NAME_REGEX.match(name):
                # if overridden: must be instance of type of overridden attribute
                for base_class in defining_base_classes:
                    base_value = base_class.__dict__[name]
                    if not isinstance(value, type(base_value)):
                        msg = (
                            f"attribute {name!r} of base class may only be overridden with a value "
                            f"which is a {type(base_value)!r}"
                        )
                        raise TypeError(msg)
            elif LOWERCASE_WORD_NAME_REGEX.match(name):
                if callable(value):
                    isasync, sig = inspect.iscoroutinefunction(value), inspect.signature(value)
                    for base_class in defining_base_classes:
                        base_value = base_class.__dict__[name]
                        if not callable(base_value):
                            msg = (
                                f"the value of {name!r} must not be callable since it is "
                                f"not callable in {base_value!r}"
                            )
                            raise TypeError(msg)
                        base_isasync = inspect.iscoroutinefunction(base_value)
                        if base_isasync != isasync:
                            if base_isasync:
                                msg = (
                                    f"the value of {name!r} must be an coroutine function "
                                    f"(defined with 'async def')"
                                )
                            else:
                                msg = f"the value of {name!r} must be an callable that is not a coroutine function"
                            raise TypeError(msg)
                        base_sig = inspect.signature(base_value, follow_wrapped=False)  # beware: slow
                        if base_sig != sig:
                            msg = f"the value of {name!r} must be an callable with this signature: {base_sig!r}"
                            raise TypeError(msg)
                else:
                    # noinspection PyUnresolvedReferences
                    if not (isinstance(value, _ToolBase.Dependency) and hasattr(value.__class__, 'Value')):
                        msg = (
                            f"the value of {name!r} must be callable or an instance of a concrete subclass of "
                            f"'dlb.ex.Tool.Dependency'"
                        )
                        raise TypeError(msg)
                    for base_class in defining_base_classes:
                        value: depend.Dependency
                        base_value = base_class.__dict__[name]
                        if callable(base_value):
                            msg = f"the value of {name!r} must be callable since it is callable in {base_value!r}"
                            raise TypeError(msg)
                        if base_value is not None and not value.compatible_and_no_less_restrictive(base_value):
                            msg = (
                                f"attribute {name!r} of base class may only be overridden by "
                                f"a {type(base_value)!r} at least as restrictive"
                            )
                            raise TypeError(msg)
            elif name not in _ToolMeta.OVERRIDEABLE_ATTRIBUTES:
                msg = (
                    f"invalid class attribute name: {name!r}\n"
                    f"  | every class attribute of a 'dlb.ex.Tool' must be named "
                    f"like 'UPPER_CASE_WORD' or 'lower_case_word"
                )
                raise AttributeError(msg)

    def _get_names(cls) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        names = dir(cls)  # from this class and its base classes

        execution_parameters = [n for n in names if UPPERCASE_WORD_NAME_REGEX.match(n)]
        execution_parameters.sort()
        execution_parameters = tuple(execution_parameters)

        dependencies = [(n, getattr(cls, n)) for n in names if LOWERCASE_WORD_NAME_REGEX.match(n)]
        dependency_infos = [
            (not isinstance(d, depend.Input), not d.required, n)
            for n, d in dependencies if isinstance(d, depend.Dependency)
        ]
        dependency_infos.sort()

        return tuple(p[-1] for p in dependency_infos), execution_parameters

    def __setattr__(cls, name, value):
        raise AttributeError

    def __delattr__(cls, name):
        raise AttributeError


# noinspection PyAbstractClass
class Tool(_ToolBase, metaclass=_ToolMeta):
    pass


def get_and_register_tool_info(tool: Type) -> ToolInfo:
    # Returns a 'ToolInfo' with a permanent local id of tool and a set of all source files in the managed tree in
    # which the class or one of its baseclasses of type 'Tool' is defined.
    #
    # The result is cached.
    #
    # The permanent local id is the same on every Python run as long as dlb.ex.platform.PERMANENT_PLATFORM_ID
    # remains the same (at least that's the idea).
    # Note however, that the behaviour of tools not only depends on their own code but also on all imported
    # objects. So, its up to the programmer of the tool, how much variability a tool with a unchanged
    # permanent local id can show.

    if not issubclass(tool, Tool):
        raise TypeError

    info = _registered_info_by_tool.get(tool)
    if info is not None:
        return info

    # collect the managed tree paths of tool and its base classes that are tools

    definition_paths = set()
    for c in reversed(tool.mro()):
        if c is not tool and issubclass(c, Tool):  # note: needs Tool with metaclass _ToolMeta, not _BaseTool
            base_info = get_and_register_tool_info(c)
            definition_paths = definition_paths.union(base_info.definition_paths)

    # noinspection PyUnresolvedReferences
    definition_path, in_archive_path, lineno = tool.definition_location

    permanent_local_id = ut.to_permanent_local_bytes((definition_path, in_archive_path, lineno))
    if definition_path is not None:
        definition_paths.add(definition_path)

    info = ToolInfo(permanent_local_tool_id=permanent_local_id, definition_paths=definition_paths)
    _registered_info_by_tool[tool] = info

    return info


def is_complete(result):
    if isinstance(result, _RunResult) and not result:
        return True
    from . import aseq
    try:
        return aseq.is_complete(result)
    except TypeError:
        raise TypeError("'result' is not a result of dlb.ex.Tool.run()") from None


# noinspection PyCallByClass
type.__setattr__(Tool, '__module__', '.'.join(_ToolBase.__module__.split('.')[:-1]))
ut.set_module_name_to_parent_by_name(vars(), [n for n in __all__ if n != 'Tool'])
ut.set_module_name_to_parent(_RunResult)
