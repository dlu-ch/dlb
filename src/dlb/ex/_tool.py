# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Dependency-aware tool execution.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = ['Tool']

import re
import os
import collections
import hashlib
import inspect
from typing import Optional, Tuple, Type

from .. import ut
from .. import di
from .. import fs
from .. import cf
from . import _error
from . import _rundb
from . import _worktree
from . import _context
from . import _depend
from . import input
from . import _dependaction
from . import _toolrun

UPPERCASE_NAME_REGEX = re.compile('^[A-Z][A-Z0-9]*(_[A-Z][A-Z0-9]*)*$')  # at least one word
LOWERCASE_MULTIWORD_NAME_REGEX = re.compile('^[a-z][a-z0-9]*(_[a-z][a-z0-9]*)+$')  # at least two words

# key: (source_path, in_archive_path, lineno), value: class with metaclass _ToolMeta
_tool_class_by_definition_location = {}

# key: dlb.ex.Tool, value: ToolInfo
_registered_info_by_tool = {}

ToolInfo = collections.namedtuple('ToolInfo', ('permanent_local_tool_id', 'definition_paths'))


def _classify_potential_method(value):
    if callable(value):
        return None, value
    elif isinstance(value, classmethod):  # not yet bound (has no __self__)
        return 'c', value.__func__  # as created by @classmethod
    elif isinstance(value, staticmethod):
        return 's', value.__func__  # as created by @staticmethod


# noinspection PyProtectedMember,PyUnresolvedReferences
class _ToolBase:
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
                    # TODO include module?
                    f"keyword argument does not name a dependency role of {self.__class__.__qualname__!r}: {name!r}\n"
                    f"  | dependency roles: {names}"
                )
                raise _error.DependencyError(msg)

            role = getattr(self.__class__, name)
            if not role.explicit:
                msg = (
                    f"keyword argument does name a non-explicit dependency role: {name!r}\n"
                    f"  | non-explicit dependency must not be assigned at construction"
                )
                raise _error.DependencyError(msg)

            if value is None:
                validated_value = None
                if role.required:
                    msg = f"keyword argument for required dependency role must not be None: {name!r}"
                    raise _error.DependencyError(msg)
            else:
                try:
                    validated_value = role.validate(value)
                except (TypeError, ValueError) as e:
                    msg = (
                        f"keyword argument for dependency role {name!r} is invalid: {value!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise _error.DependencyError(msg)

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
                        raise _error.DependencyError(msg)
                    object.__setattr__(self, name, None)
                else:
                    object.__setattr__(self, name, NotImplemented)
            if role.explicit:
                # this remains unchanged between dlb run if dlb.ex._platform.PERMANENT_PLATFORM_ID remains unchanged
                try:
                    action = _dependaction.get_action(role, name)
                    dependency_fingerprint = action.get_permanent_local_instance_id()

                    validated_values = role.tuple_from_value(getattr(self, name))
                    dependency_fingerprint += action.get_permanent_local_value_id(validated_values)

                    # since 'dependency_names' and 'r.explicit of all their members r are fixed for all instances
                    # of this class, the order of dependency roles is sufficient for their identification
                    hashalg.update(dependency_fingerprint)  # dependency_fingerprint must not be empty
                except KeyError:
                    msg = f"keyword names unregistered dependency class {role.__class__!r}: {name!r}"
                    raise _error.DependencyError(msg)

        # permanent local tool instance fingerprint for this instance (do not compare fingerprint between
        # different self.__class__!)
        object.__setattr__(self, 'fingerprint', hashalg.digest())  # always 20 byte

    # final
    def start(self, *, force_redo: bool = False):
        with di.Cluster('prepare tool instance', level=cf.level.run_preparation, with_time=True, is_progress=True):
            # noinspection PyTypeChecker
            context: _context.Context = _context.Context.active

            dependency_actions = tuple(
                _dependaction.get_action(getattr(self.__class__, n), n)
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
                    raise _error.ExecutionParameterError(msg) from None
            if len(execution_parameter_digest) >= 20:
                execution_parameter_digest = hashlib.sha1(execution_parameter_digest).digest()

            db = _context._get_rundb()

            tool_instance_dbid = db.get_and_register_tool_instance_dbid(
                get_and_register_tool_info(self.__class__).permanent_local_tool_id,
                self.fingerprint)
            di.inform(f"tool instance is {tool_instance_dbid!r}", level=cf.level.run_preparation)

            result_proxy_of_last_run = context._get_pending_result_proxy_for(tool_instance_dbid)
            if result_proxy_of_last_run is not None:
                with di.Cluster('wait for last redo to complete', level=cf.level.run_serialization,
                                with_time=True, is_progress=True):
                    result_proxy_of_last_run.complete()

        with di.Cluster(f'check redo necessity for tool instance {tool_instance_dbid!r}',
                        level=cf.level.redo_necessity_check, with_time=True, is_progress=True):

            with di.Cluster('explicit input dependencies', level=cf.level.redo_necessity_check,
                            with_time=True, is_progress=True):
                memo_by_encoded_path = \
                    _toolrun.check_and_memorize_explicit_fs_input_dependencies(self, dependency_actions, context)

                # treat all files used for definition of self.__class__ like explicit input dependencies if they
                # have a managed tree path.
                definition_file_count = 0
                for pn in get_and_register_tool_info(self.__class__).definition_paths:
                    try:
                        p = context.working_tree_path_of(fs.Path.Native(pn), existing=True, collapsable=False)
                        encoded_path = _rundb.encode_path(p)
                        memo = memo_by_encoded_path.get(encoded_path)
                        if memo is None:
                            memo = _worktree.read_filesystem_object_memo(context.root_path / p)  # may raise OSError
                        assert memo.stat is not None
                        definition_file_count += 1
                        memo_by_encoded_path[encoded_path] = memo
                        assert memo.stat is not None
                    except (ValueError, OSError):
                        # silently ignore all definition files not in managed tree
                        pass
                di.inform(f"added {definition_file_count} tool definition files as input dependency",
                          level=cf.level.redo_necessity_check)

            # 'memo_by_encoded_path' contains a current memo for every filesystem object in the managed tree that
            # is an explicit input dependency of this call of 'start()' or an non-explicit input dependency of the
            # last successful redo of the same tool instance according to the run-database

            with di.Cluster('explicit output dependencies', level=cf.level.redo_necessity_check,
                            with_time=True, is_progress=True):
                encoded_paths_of_explicit_input_dependencies = set(memo_by_encoded_path.keys())
                dependency_action_by_path, obstructive_paths, needs_redo = \
                    _toolrun.check_explicit_fs_output_dependencies(
                        self, dependency_actions, encoded_paths_of_explicit_input_dependencies, False, context)

            with di.Cluster('input dependencies of the last redo', level=cf.level.redo_necessity_check,
                            with_time=True, is_progress=True):
                db = _context._get_rundb()
                inputs_from_last_redo = db.get_fsobject_inputs(tool_instance_dbid)
                for encoded_path, (is_explicit, last_encoded_memo) in inputs_from_last_redo.items():
                    if not is_explicit and encoded_path not in memo_by_encoded_path:
                        memo, needs_redo = _toolrun.get_memo_for_fs_input_dependency_from_rundb(
                            encoded_path, last_encoded_memo, needs_redo, context.root_path)
                        memo_by_encoded_path[encoded_path] = memo  # memo.state may be None

            # 'memo_by_encoded_path' contains a current memo for every filesystem object in the managed tree that
            # is an explicit or non-explicit input dependency of this call of 'start()' or an non-explicit input
            # dependency of the last successful redo of the same tool instance according to the run-database

            with di.Cluster('environment variables', level=cf.level.redo_necessity_check,
                            with_time=True, is_progress=True):
                envvar_value_by_name, envvar_digest = \
                    _toolrun.check_envvar_dependencies(self, dependency_actions, context)

            if not needs_redo and force_redo:
                di.inform("redo requested by start()", level=cf.level.redo_reason)
                needs_redo = True

            if not needs_redo:
                redo_state_in_db = db.get_redo_state(tool_instance_dbid)
                redo_request_in_db = redo_state_in_db.get(_rundb.Aspect.RESULT.value)
                if redo_request_in_db is None:
                    di.inform("redo necessary because not run before", level=cf.level.redo_reason)
                    needs_redo = True
                else:
                    redo_request_in_db = bool(redo_request_in_db)
                    execution_parameter_digest_in_db = redo_state_in_db.get(
                        _rundb.Aspect.EXECUTION_PARAMETERS.value, b'')
                    envvar_digest_in_db = redo_state_in_db.get(_rundb.Aspect.ENVIRONMENT_VARIABLES.value, b'')
                    if redo_request_in_db is True:
                        di.inform("redo requested by last successful redo", level=cf.level.redo_reason)
                        needs_redo = True
                    elif execution_parameter_digest != execution_parameter_digest_in_db:
                        di.inform("redo necessary because of changed execution parameter", level=cf.level.redo_reason)
                        needs_redo = True
                    elif envvar_digest != envvar_digest_in_db:
                        di.inform("redo necessary because of changed environment variable", level=cf.level.redo_reason)
                        needs_redo = True

            if not needs_redo:
                with di.Cluster('compare input dependencies with state before last successful redo',
                                level=cf.level.redo_necessity_check, with_time=True, is_progress=True):
                    # sorting not necessary for repeatability
                    for encoded_path, memo in memo_by_encoded_path.items():
                        is_explicit, last_encoded_memo = inputs_from_last_redo.get(encoded_path, (True, None))
                        assert memo.stat is not None or not is_explicit
                        redo_reason = _rundb.compare_fsobject_memo_to_encoded_from_last_redo(
                            memo, last_encoded_memo, encoded_path in encoded_paths_of_explicit_input_dependencies)
                        if redo_reason is not None:
                            path = _rundb.decode_encoded_path(encoded_path)
                            msg = (
                                f"redo necessary because of filesystem object: {path.as_string()!r}\n"
                                f"    reason: {redo_reason}"
                            )
                            di.inform(msg, level=cf.level.redo_reason)
                            needs_redo = True
                            break
                        # TODO redo if mtime of true input not in the past (G-D4)

        if not needs_redo:
            _context._register_successful_run(False)
            return _toolrun.RunResult(self, False)  # no redo

        if obstructive_paths:
            with di.Cluster('remove obstructive filesystem objects that are explicit output dependencies',
                            level=cf.level.redo_preparation, with_time=True, is_progress=True):
                with context.temporary(is_dir=True) as tmp_dir:
                    for p in obstructive_paths:
                        _worktree.remove_filesystem_object(context.root_path / p, abs_empty_dir_path=tmp_dir,
                                                           ignore_non_existent=True)

        result = _toolrun.RunResult(self, True)
        for action in dependency_actions:
            if not action.dependency.explicit and action.dependency.Value is input.EnvVar.Value:
                try:
                    value = envvar_value_by_name.get(action.dependency.name)
                    setattr(result, action.name, value)  # validates on assignment
                except (TypeError, ValueError) as e:
                    msg = (
                        f"input dependency {action.name!r} cannot use environment variable {action.dependency.name!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise _error.RedoError(msg) from None

        # note: no db.commit() necessary as long as root context does commit on exception
        redo_sequencer = context._redo_sequencer
        tid = redo_sequencer.wait_then_start(
            context.max_parallel_redo_count, None, self._redo_with_aftermath,
            result=result, context=_toolrun.RedoContext(context, dependency_action_by_path),
            dependency_actions=dependency_actions, memo_by_encoded_path=memo_by_encoded_path,
            encoded_paths_of_explicit_input_dependencies=encoded_paths_of_explicit_input_dependencies,
            execution_parameter_digest=execution_parameter_digest, envvar_digest=envvar_digest,
            db=db, tool_instance_dbid=tool_instance_dbid)

        return redo_sequencer.create_result_proxy(tid, uid=tool_instance_dbid, expected_class=_toolrun.RunResult)

    async def _redo_with_aftermath(self, result, context,
                                   dependency_actions, memo_by_encoded_path,
                                   encoded_paths_of_explicit_input_dependencies,
                                   execution_parameter_digest, envvar_digest,
                                   db, tool_instance_dbid):
        # note: no db.commit() necessary as long as root context does commit on exception
        di.inform(f"start redo for tool instance {tool_instance_dbid!r}", level=cf.level.redo_start, with_time=True)
        redo_request = bool(await self.redo(result, context))

        with di.Cluster(f"memorize successful redo for tool instance {tool_instance_dbid!r}",
                        level=cf.level.redo_aftermath, with_time=True):
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
                            raise _error.RedoError(msg)
                        validated_value = None
                        setattr(result, action.name, validated_value)
                    if action.dependency.Value is fs.Path:
                        if isinstance(action.dependency, _depend.InputDependency):
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
                                        raise _error.RedoError(msg) from None
                                # absolute paths to the management tree are silently ignored
                                if not p.is_absolute():
                                    encoded_paths_of_nonexplicit_input_dependencies.add(_rundb.encode_path(p))
                        elif isinstance(action.dependency, _depend.OutputDependency):
                            paths = action.dependency.tuple_from_value(validated_value)
                            for p in paths:
                                try:
                                    p = context.working_tree_path_of(p, existing=True, collapsable=False)
                                except ValueError:
                                    msg = (
                                        f"non-explicit output dependency {action.name!r} contains a path "
                                        f"that is not a managed tree path: {p.as_string()!r}"
                                    )
                                    raise _error.RedoError(msg) from None
                                encoded_paths_of_modified_output_dependencies.add(_rundb.encode_path(p))

            encoded_paths_of_input_dependencies = \
                encoded_paths_of_explicit_input_dependencies | encoded_paths_of_nonexplicit_input_dependencies
            for p in context.modified_outputs:
                encoded_paths_of_modified_output_dependencies.add(_rundb.encode_path(p))

            with di.Cluster('store state before redo in run-database', level=cf.level.redo_aftermath):
                # redo was successful, so save the state before the redo to the run-database
                info_by_fsobject_dbid = {
                    encoded_path: (
                        encoded_path in encoded_paths_of_explicit_input_dependencies,
                        _rundb.encode_fsobject_memo(memo))
                    for encoded_path, memo in memo_by_encoded_path.items()
                    if encoded_path in encoded_paths_of_input_dependencies  # drop obsolete non-explicit dependencies
                }
                info_by_fsobject_dbid.update({  # add new non-explicit dependencies
                    encoded_path: (False, None)
                    for encoded_path in encoded_paths_of_nonexplicit_input_dependencies - set(info_by_fsobject_dbid)
                })

                db.commit_if_overdue()
                db.update_dependencies_and_state(
                    tool_instance_dbid,
                    info_by_encoded_path=info_by_fsobject_dbid,
                    memo_digest_by_aspect={
                        _rundb.Aspect.RESULT.value:
                            b'\x01' if redo_request else b'',
                        _rundb.Aspect.EXECUTION_PARAMETERS.value:
                            execution_parameter_digest if execution_parameter_digest else None,
                        _rundb.Aspect.ENVIRONMENT_VARIABLES.value:
                            envvar_digest if envvar_digest else None
                    },
                    encoded_paths_of_modified=encoded_paths_of_modified_output_dependencies)

            # note: no db.commit() necessary as long as root context does commit on exception

        _context._register_successful_run(True)

        return result

    async def redo(self, result: 'dlb.ex.RunResult', context: 'dlb.ex.RedoContext') -> Optional[bool]:
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


class _ToolMeta(type):

    OVERRIDEABLE_ATTRIBUTES = frozenset(('redo', '__doc__', '__module__', '__annotations__'))

    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)

        # prevent attributes of _ToolBase from being overridden
        protected_attrs = (set(_ToolBase.__dict__.keys()) - _ToolMeta.OVERRIDEABLE_ATTRIBUTES | {'__new__'})
        attrs = set(cls.__dict__) & protected_attrs
        if attrs:
            raise AttributeError("must not be overridden in a 'dlb.ex.Tool': {}".format(repr(sorted(attrs)[0])))
        cls._check_own_attributes()
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
            raise _error.DefinitionAmbiguityError(msg)

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
            raise _error.DefinitionAmbiguityError(msg) from None

        location = source_path, in_archive_path, source_lineno
        existing_location = _tool_class_by_definition_location.get(location)
        if existing_location is not None:
            msg = (
                f"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
                f"  | location: {source_path!r}:{source_lineno}\n"
                f"  | class: {existing_location!r}"
            )
            raise _error.DefinitionAmbiguityError(msg)

        return location

    def _check_own_attributes(cls):
        for name, value in cls.__dict__.items():
            defining_base_classes = tuple(c for c in cls.__bases__ if name in c.__dict__)
            if UPPERCASE_NAME_REGEX.match(name):
                # if overridden: must be instance of type of overridden attribute
                for base_class in defining_base_classes:
                    base_value = base_class.__dict__[name]
                    if not isinstance(value, type(base_value)):
                        msg = (
                            f"attribute {name!r} of base class may only be overridden with a value "
                            f"which is a {type(base_value)!r}"
                        )
                        raise TypeError(msg)
            elif LOWERCASE_MULTIWORD_NAME_REGEX.match(name):
                method_kind = _classify_potential_method(value)
                if method_kind is not None:
                    for base_class in defining_base_classes:
                        base_value = base_class.__dict__[name]
                        base_method_kind = _classify_potential_method(base_value)
                        if base_method_kind is None:
                            msg = f"attribute {name!r} must not be a method since it is not a method in {base_value!r}"
                            raise TypeError(msg)

                        method_k, func = method_kind
                        sig = inspect.signature(func)
                        base_method_kind, base_func = base_method_kind
                        base_sig = inspect.signature(base_func, follow_wrapped=False)  # beware: slow
                        if (method_k, sig) != (base_method_kind, base_sig):
                            base_method_descr = '{} method'.format({
                                None: '(instance)',
                                'c': 'class',
                                's': 'static'
                            }[base_method_kind])
                            msg = f"attribute {name!r} must be a {base_method_descr} with this signature: {base_sig!r}"
                            raise TypeError(msg)

                        isasync = inspect.iscoroutinefunction(func)
                        base_isasync = inspect.iscoroutinefunction(base_func)
                        if isasync != base_isasync:
                            if base_isasync:
                                msg = f"attribute {name!r} must be a coroutine function (defined with 'async def')"
                            else:
                                msg = f"attribute {name!r} must not be a coroutine function (defined with 'async def')"
                            raise TypeError(msg)
                else:
                    # noinspection PyUnresolvedReferences
                    if not (isinstance(value, _depend.Dependency) and hasattr(value.__class__, 'Value')):
                        msg = (
                            f"attribute {name!r} must be a method or an instance of a "
                            f"concrete subclass of 'dlb.ex.Dependency'"
                        )
                        raise TypeError(msg)
                    for base_class in defining_base_classes:
                        value: _depend.Dependency
                        base_value = base_class.__dict__[name]
                        if _classify_potential_method(base_value) is not None:
                            msg = f"attribute {name!r} must be a method since it is a method in {base_value!r}"
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
                    f"like 'UPPER_CASE' or 'lower_case' (at least two words)"
                )
                raise AttributeError(msg)

    def _get_names(cls) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        names = dir(cls)  # from this class and its base classes

        execution_parameters = [n for n in names if UPPERCASE_NAME_REGEX.match(n)]
        execution_parameters.sort()
        execution_parameters = tuple(execution_parameters)

        dependencies = [(n, getattr(cls, n)) for n in names if LOWERCASE_MULTIWORD_NAME_REGEX.match(n)]
        dependency_infos = [
            (not isinstance(d, _depend.InputDependency), not d.required, n)
            for n, d in dependencies if isinstance(d, _depend.Dependency)
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
    # The permanent local id is the same on every Python run as long as dlb.ex._platform.PERMANENT_PLATFORM_ID
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


# noinspection PyCallByClass
type.__setattr__(Tool, '__module__', '.'.join(_ToolBase.__module__.split('.')[:-1]))  # circumvent write protection
ut.set_module_name_to_parent_by_name(vars(), [n for n in __all__ if n != 'Tool'])
