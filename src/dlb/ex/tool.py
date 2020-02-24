# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Dependency-aware tool execution."""

__all__ = ('Tool', 'DefinitionAmbiguityError', 'DependencyRoleAssignmentError', 'DependencyCheckError', 'RedoError')

import sys
import re
import os
import stat
import collections
import hashlib
import logging
import inspect
import marshal
from typing import Type, Optional, Dict, Tuple, Set
from .. import ut
from .. import fs
from ..fs import manip
from .. import di
from . import rundb
from . import context as context_
from . import depend
from . import dependaction
assert sys.version_info >= (3, 7)


EXECUTION_PARAMETER_NAME_REGEX = re.compile('^[A-Z][A-Z0-9]*(_[A-Z][A-Z0-9]*)*$')
assert EXECUTION_PARAMETER_NAME_REGEX.match('A')
assert EXECUTION_PARAMETER_NAME_REGEX.match('A2_B')
assert not EXECUTION_PARAMETER_NAME_REGEX.match('_A')

DEPENDENCY_NAME_REGEX = re.compile('^[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$')
assert DEPENDENCY_NAME_REGEX.match('object_file')
assert not DEPENDENCY_NAME_REGEX.match('_object_file_')
assert not DEPENDENCY_NAME_REGEX.match('Object_file_')


# key: (source_path, in_archive_path, lineno), value: class with metaclass _ToolMeta
_tool_class_by_definition_location = {}

# key: dlb.ex.Tool, value: ToolInfo
_registered_info_by_tool = {}


class DefinitionAmbiguityError(SyntaxError):
    pass


class DependencyRoleAssignmentError(ValueError):
    pass


class DependencyCheckError(Exception):
    pass


class RedoError(Exception):
    pass


ToolInfo = collections.namedtuple('ToolInfo', ('permanent_local_tool_id', 'definition_paths'))


def _get_memo_for_fs_input_dependency(name: Optional[str], path: fs.Path,
                                      memo_by_encoded_path: Dict[str, manip.FilesystemObjectMemo],
                                      context: context_.Context) -> Tuple[str, manip.FilesystemObjectMemo]:
    # Returns the tuple (encoded_path, memo) where encoded_path is the encoded managed tree path for *path* and *memo*
    # is the FilesystemObjectMemo for the filesystem object with this managed tree path in *context*.
    # memo.stat is not None.
    #
    # *memo_by_encoded_path* is used as a cache for *memo*. If it contains *encoded_path* as a key, its value is
    # used as *memo*. Otherwise *memo* is read from the filesystem.
    #
    # Raises DependencyCheckError if *path* is not a the path of an existing filesystem object in the managed
    # tree that has a managed tree path.
    #
    # *name* is thee name of the dependency role which contains *path* as a validated value. It is used in a
    # possible exception message.

    path_role = 'is' if name is None else f"input dependency {name!r} contains"
    try:
        try:
            path = context.managed_tree_path_of(path, existing=True, collapsable=False)
        except ValueError as e:
            if isinstance(e, manip.PathNormalizationError) and e.oserror is not None:
                raise e.oserror
            msg = (
                f"{path_role} a path that is not a managed tree path: {path.as_string()!r}\n"
                f"  | reason: {ut.exception_to_line(e)}"
            )
            raise DependencyCheckError(msg) from None

        encoded_path = rundb.encode_path(path)
        memo = memo_by_encoded_path.get(encoded_path)
        if memo is None:
            memo = manip.read_filesystem_object_memo(context.root_path / path)  # may raise OSError
        assert memo.stat is not None
    except FileNotFoundError:
        msg = f"{path_role} a path of an non-existing filesystem object: {path.as_string()!r}"
        raise DependencyCheckError(msg) from None
    except OSError as e:
        msg = (
            f"{path_role} a path of an inaccessible filesystem object: {path.as_string()!r}\n"
            f"  | reason: {ut.exception_to_line(e)}"
        )
        raise DependencyCheckError(msg) from None

    return encoded_path, memo


def _get_memo_for_fs_input_dependency_from_rundb(encoded_path: str, last_encoded_memo: Optional[bytes],
                                                 needs_redo: bool, context: context_.Context) \
        -> Tuple[manip.FilesystemObjectMemo, bool]:

    path = None
    memo = manip.FilesystemObjectMemo()

    try:
        path = rundb.decode_encoded_path(encoded_path)  # may raise ValueError
    except ValueError:
        if not needs_redo:
            di.inform(f"redo necessary because of invalid encoded path: {encoded_path!r}",
                      level=logging.WARNING)
            needs_redo = True

    if path is None:
        return memo, needs_redo

    try:

        try:
            path = context.managed_tree_path_of(path, existing=True, collapsable=False)
            memo = manip.read_filesystem_object_memo(context.root_path / path)
        except FileNotFoundError:
            # ignore if did not exist according to valid 'encoded_memo'
            did_not_exist_before_last_redo = False
            try:
                did_not_exist_before_last_redo = \
                    last_encoded_memo is None or rundb.decode_encoded_fsobject_memo(last_encoded_memo).stat is None
            except ValueError:
                pass
            if not did_not_exist_before_last_redo:
                raise

    except (ValueError, OSError):
        if not needs_redo:
            msg = (
                f"redo necessary because of inexisting or inaccessible "
                f"filesystem object: {path.as_string()!r}"  # also if not in managed tree
            )
            di.inform(msg, level=logging.INFO)
            needs_redo = True  # comparision not possible -> redo

    return memo, needs_redo  # memo.state may be None


def _check_input_memo_for_redo(memo: manip.FilesystemObjectMemo, last_encoded_memo: Optional[bytes],
                               is_explicit: bool) -> Optional[str]:
    # Compares the present *memo* if a filesystem object in the managed tree that is an input dependency with its
    # last known encoded state *last_encoded_memo*, if any.
    #
    # Returns ``None`` if no redo is necessary due to the difference of *memo* and *last_encoded_memo* and
    # a short line describing the reason otherwise.

    if last_encoded_memo is None:
        if is_explicit:
            return 'was an output dependency of a redo'
        return 'was an new dependency or an output dependency of a redo'

    try:
        last_memo = rundb.decode_encoded_fsobject_memo(last_encoded_memo)
    except ValueError:
        return 'state before last successful redo is unknown'

    if is_explicit:
        assert memo.stat is not None
        if last_memo.stat is None:
            return 'filesystem object did not exist'
    elif (memo.stat is None) != (last_memo.stat is None):
        return 'existence has changed'
    elif memo.stat is None:
        # non-explicit dependency of a filesystem object that does not exist and did not exist before the
        # last successful redo
        return None

    assert memo.stat is not None
    assert last_memo.stat is not None

    if stat.S_IFMT(memo.stat.mode) != stat.S_IFMT(last_memo.stat.mode):
        return 'type of filesystem object has changed'

    if stat.S_ISLNK(memo.stat.mode) and memo.symlink_target != last_memo.symlink_target:
        return 'symbolic link target has changed'

    if memo.stat.size != last_memo.stat.size:
        return 'size has changed'

    if memo.stat.mtime_ns != last_memo.stat.mtime_ns:
        return 'mtime has changed'

    if (memo.stat.mode, memo.stat.uid, memo.stat.gid) != \
            (last_memo.stat.mode, last_memo.stat.uid, last_memo.stat.gid):
        return 'permissions or owner have changed'


def _check_and_memorize_explicit_input_dependencies(tool, dependency_actions: Tuple[dependaction.Action, ...],
                                                    context: context_.Context) \
        -> Dict[str, manip.FilesystemObjectMemo]:

    # For all explicit input dependencies of *tool* in *dependency_actions* for filesystem objects:
    # Checks existence, reads and checks its FilesystemObjectMemo.
    #
    # Treats all definitions file of this tool class that are in the managed tree as explicit input dependencies.
    #
    # Returns a dictionary whose key are encoded managed tree paths and whose values are the corresponding
    # FilesystemObjectMemo m with ``m.stat is not None``.

    memo_by_encoded_path = {}

    with di.Cluster('from dependency roles', is_progress=True):
        for action in dependency_actions:
            # read memo of each filesystem object of a explicit input dependency in a reproducible order
            if action.dependency.explicit and isinstance(action.dependency, depend.Input) and \
                    isinstance(action.dependency, depend.FilesystemObject):
                with di.Cluster(f"dependency role {action.name!r}", is_progress=True):
                    validated_value_tuple = action.dependency.tuple_from_value(getattr(tool, action.name))
                    for p in validated_value_tuple:  # p is a dlb.fs.Path
                        try:
                            encoded_path, memo = _get_memo_for_fs_input_dependency(
                                action.name, p, memo_by_encoded_path, context)
                            action.check_filesystem_object_memo(memo)  # raise ValueError if memo is not as expected
                            memo_by_encoded_path[encoded_path] = memo
                            assert memo.stat is not None
                        except ValueError as e:
                            msg = (
                                f"invalid value of dependency {action.name!r}: {p.as_string()!r}\n"
                                f"  | reason: {ut.exception_to_line(e)}"
                            )
                            raise DependencyCheckError(msg) from None

    with di.Cluster(f"from tool definition files", is_progress=True):
        # treat all files used for definition of self.__class__ like explicit input dependencies if they
        # have a managed tree path.
        definition_file_count = 0
        for p in get_and_register_tool_info(tool.__class__).definition_paths:
            try:
                encoded_path, memo = _get_memo_for_fs_input_dependency(
                    None, fs.Path(p), memo_by_encoded_path, context)
                definition_file_count += 1  # TODO test
                memo_by_encoded_path[encoded_path] = memo
                assert memo.stat is not None
            except (ValueError, DependencyCheckError):
                # silently ignore all definition files not in managed tree
                pass
        di.inform(f"added {definition_file_count} files as input dependencies")

    return memo_by_encoded_path


def _check_explicit_output_dependencies(tool, dependency_actions: Tuple[dependaction.Action, ...],
                                        encoded_paths_of_explicit_input_dependencies: Set[str],
                                        needs_redo: bool,
                                        context: context_.Context) -> bool:
    # For all explicit output dependencies of *tool* in *dependency_actions* for filesystem objects:
    # Checks existence, reads and checks its FilesystemObjectMemo.
    #
    # Returns ``True`` if at least one of the filesystem objects does not exist.

    for action in dependency_actions:

        # read memo of each filesystem object of a explicit input dependency in a reproducible order
        if action.dependency.explicit and isinstance(action.dependency, depend.Output) and \
                isinstance(action.dependency, depend.FilesystemObject):

            validated_value_tuple = action.dependency.tuple_from_value(getattr(tool, action.name))
            for p in validated_value_tuple:  # p is a dlb.fs.Path
                try:
                    p = context.managed_tree_path_of(p, existing=True, collapsable=True)
                except ValueError as e:
                    msg = (
                        f"output dependency {action.name!r} contains a path that is not a managed tree path: "
                        f"{p.as_string()!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise DependencyCheckError(msg) from None
                if rundb.encode_path(p) in encoded_paths_of_explicit_input_dependencies:
                    msg = (
                        f"output dependency {action.name!r} contains a path that is also an explicit "
                        f"input dependency: {p.as_string()!r}"
                    )
                    raise DependencyCheckError(msg)
                try:
                    memo = manip.read_filesystem_object_memo(context.root_path / p)
                    action.check_filesystem_object_memo(memo)  # raise ValueError if memo is not as expected
                except (ValueError, OSError) as e:
                    if not needs_redo:
                        msg = (
                            f"redo necessary because of filesystem object that "
                            f"is an output dependency: {p.as_string()!r}\n"
                            f"    reason: {ut.exception_to_line(e)}"
                        )
                        di.inform(msg)
                        needs_redo = True

    return needs_redo


def _remove_explicit_output_dependencies(tool, dependency_actions: Tuple[dependaction.Action, ...],
                                         context: context_.Context):
    # Remove all filesystem objects that are explicit output dependencies of *tool*.

    tmp_dir = None
    db = context_._get_rundb()

    for action in dependency_actions:
        if action.dependency.explicit and isinstance(action.dependency, depend.Output) and \
                isinstance(action.dependency, depend.FilesystemObject):
            validated_value_tuple = action.dependency.tuple_from_value(getattr(tool, action.name))
            for p in validated_value_tuple:  # p is a (valid) managed tree path as a dlb.fs.Path
                if tmp_dir is None:
                    tmp_dir = context.create_temporary(is_dir=True)  # may raise OSError
                manip.remove_filesystem_object(context.root_path / p,
                                               abs_empty_dir_path=tmp_dir,
                                               ignore_non_existing=True)  # may raise OSError
                encoded_path = rundb.encode_path(p)
                db.declare_fsobject_input_as_modified(encoded_path)

    if tmp_dir is not None:
        try:
            manip.remove_filesystem_object(tmp_dir)
        except OSError:
            pass  # try again when root context is cleaned-up


class _RedoResult:
    # Attribute represent concrete dependencies of a tool instance.
    # Explicit dependencies are referred to the tool instance.
    # Non-explicit dependencies can be set exactly once.
    #
    # To be used by redo.

    def __init__(self, tool):
        super().__setattr__('_tool', tool)

    def __setattr__(self, key, value):
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
                    f"keyword argument does not name a dependency role of {self.__class__.__qualname__!r}: {name!r}\n"
                    f"  | dependency roles: {names}"
                )
                raise DependencyRoleAssignmentError(msg)

            role = getattr(self.__class__, name)
            if not role.explicit:
                msg = (
                    f"keyword argument does name a non-explicit dependency role: {name!r}\n"
                    f"  | non-explicit dependency must not be assigned at construction"
                )
                raise DependencyRoleAssignmentError(msg)

            if value is None:
                validated_value = None
                if role.required:
                    msg = f"keyword argument for required dependency role must not be None: {name!r}"
                    raise DependencyRoleAssignmentError(msg)
            else:
                validated_value = role.validate(value)

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
                        raise DependencyRoleAssignmentError(msg)
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
                    raise DependencyRoleAssignmentError(msg)

        # permanent local tool instance fingerprint for this instance (do not compare fingerprint between
        # different self.__class__!)
        object.__setattr__(self, 'fingerprint', hashalg.digest())  # always 20 byte

    # final
    def run(self):
        with di.Cluster('run tool instance', with_time=True, is_progress=True):

            dependency_actions = tuple(
                dependaction.get_action(getattr(self.__class__, n), n)
                for n in self.__class__._dependency_names
            )

            # noinspection PyTypeChecker
            context: context_.Context = context_.Context.active
            db = context_._get_rundb()

            tool_instance_dbid = db.get_and_register_tool_instance_dbid(
                get_and_register_tool_info(self.__class__).permanent_local_tool_id,
                self.fingerprint)
            di.inform(f"tool instance dbid is {tool_instance_dbid!r}")

            with di.Cluster('prepare'):

                with di.Cluster('filesystem objects that are explicit input dependencies',
                                with_time=True, is_progress=True):
                    memo_by_encoded_path = _check_and_memorize_explicit_input_dependencies(
                        self, dependency_actions, context)

                # 'memo_by_encoded_path' contains a current memo for every filesystem object in the managed tree that
                # is an explicit input dependency of this call of 'run()' or an non-explicit input dependency of the
                # last successful redo of the same tool instance according to the run-database

                with di.Cluster('filesystem objects that are explicit output dependencies',
                                with_time=True, is_progress=True):
                    encoded_paths_of_explicit_input_dependencies = set(memo_by_encoded_path.keys())
                    needs_redo = _check_explicit_output_dependencies(
                        self, dependency_actions, encoded_paths_of_explicit_input_dependencies, False, context)

                with di.Cluster('filesystem objects that were input dependencies of the last redo',
                                with_time=True, is_progress=True):
                    db = context_._get_rundb()
                    inputs_from_last_redo = db.get_fsobject_inputs(tool_instance_dbid)
                    for encoded_path, (is_explicit, last_encoded_memo) in inputs_from_last_redo.items():
                        if not is_explicit and encoded_path not in memo_by_encoded_path:
                            memo, needs_redo = _get_memo_for_fs_input_dependency_from_rundb(
                                encoded_path, last_encoded_memo, needs_redo, context)
                            memo_by_encoded_path[encoded_path] = memo  # memo.state may be None

                # 'memo_by_encoded_path' contains a current memo for every filesystem object in the managed tree that
                # is an explicit or non-explicit input dependency of this call of 'run()' or an non-explicit input
                # dependency of the last successful redo of the same tool instance according to the run-database

                if not needs_redo:
                    with di.Cluster('compare input dependencies with state before last successful redo',
                                    with_time=True, is_progress=True):
                        # sorting not necessary for repeatability
                        for encoded_path, memo in memo_by_encoded_path.items():
                            is_explicit, last_encoded_memo = inputs_from_last_redo.get(encoded_path, (True, None))
                            assert memo.stat is not None or not is_explicit
                            redo_reason = _check_input_memo_for_redo(
                                memo, last_encoded_memo, encoded_path in encoded_paths_of_explicit_input_dependencies)
                            if redo_reason is not None:
                                path = rundb.decode_encoded_path(encoded_path)
                                msg = (
                                    f"redo necessary because of filesystem object: {path.as_string()!r}\n"
                                    f"    reason: {redo_reason}"
                                )
                                di.inform(msg)
                                needs_redo = True
                                break

            if not needs_redo:
                return None  # no redo

            with di.Cluster('remove filesystem objects that are explicit output dependencies',
                            with_time=True, is_progress=True):
                _remove_explicit_output_dependencies(self, dependency_actions, context)

            result = _RedoResult(self)

            for action in dependency_actions:
                if not action.dependency.explicit and getattr(result, action.name) is NotImplemented:
                    try:
                        value = action.get_initial_result_for_nonexplicit(context)
                        if value is not NotImplemented:
                            setattr(result, action.name, value)
                    except ValueError as e:
                        raise RedoError(*e.args)

            with di.Cluster('redo', with_time=True, is_progress=True):
                # note: no db.commit() necessary as long as root context does commit on exception
                self.redo(result, context)

                # collect non-explicit input dependencies of this redo
                encoded_paths_of_nonexplicit_input_dependencies = set()
                for action in dependency_actions:
                    if not action.dependency.explicit and isinstance(action.dependency, depend.Input):
                        validated_value = getattr(result, action.name)
                        if validated_value is NotImplemented:
                            if action.dependency.required:
                                msg = (
                                    f"non-explicit input dependency not assigned during redo: {action.name!r}\n"
                                    f"  | use 'result.{action.name} = ...' in body of redo(self, result, context)"
                                )
                                raise RedoError(msg)
                            validated_value = None
                            setattr(result, action.name, validated_value)
                        if isinstance(action.dependency, depend.FilesystemObject):
                            paths = action.dependency.tuple_from_value(validated_value)
                            for p in paths:
                                try:
                                    p = context.managed_tree_path_of(p, existing=True, collapsable=False)
                                except ValueError:
                                    msg = (
                                        f"non-explicit input dependency {action.name!r} contains a path that is not a "
                                        f"managed tree path: {p.as_string()!r}"
                                    )
                                    raise RedoError(msg) from None
                                encoded_paths_of_nonexplicit_input_dependencies.add(rundb.encode_path(p))

            encoded_paths_of_input_dependencies = \
                encoded_paths_of_explicit_input_dependencies | encoded_paths_of_nonexplicit_input_dependencies

            with di.Cluster('store state before redo in run-database'):
                # redo was successful, so save the state before the redo to the run-database
                info_by_by_fsobject_dbid = {
                    encoded_path: (
                        encoded_path in encoded_paths_of_explicit_input_dependencies,
                        rundb.encode_fsobject_memo(memo))
                    for encoded_path, memo in memo_by_encoded_path.items()
                    if encoded_path in encoded_paths_of_input_dependencies  # drop obsolete non-explicit dependencies
                }
                info_by_by_fsobject_dbid.update({  # add new non-explicit dependencies
                    encoded_path: (False, None)
                    for encoded_path in encoded_paths_of_nonexplicit_input_dependencies - set(info_by_by_fsobject_dbid)
                })
                db.replace_fsobject_inputs(tool_instance_dbid, info_by_by_fsobject_dbid)
                # note: no db.commit() necessary as long as root context does commit on exception

            return result

    def redo(self, result: _RedoResult, context: context_.Context):
        raise NotImplementedError

    def __setattr__(self, name: str, value):
        raise AttributeError

    def __delattr__(self, name: str):
        raise AttributeError

    def __repr__(self):
        names = self.__class__._dependency_names
        args = ', '.join('{}={}'.format(n, repr(getattr(self, n))) for n in names)
        return f'{self.__class__.__qualname__}({args})'


# noinspection PyProtectedMember
depend._inject_into(_ToolBase, 'Tool', '.'.join(_ToolBase.__module__.split('.')[:-1]))


class _ToolMeta(type):

    OVERRIDEABLE_ATTRIBUTES = frozenset(('redo', '__doc__', '__module__'))

    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)

        # prevent attributes of _ToolBase from being overridden
        if cls is not _ToolBase:
            protected_attrs = (set(_ToolBase.__dict__.keys()) - _ToolMeta.OVERRIDEABLE_ATTRIBUTES | {'__new__'})
            attrs = set(cls.__dict__) & protected_attrs
            if attrs:
                raise AttributeError("must not be overridden in a 'dlb.ex.Tool': {}".format(repr(sorted(attrs)[0])))
            cls.check_own_attributes()

        super().__setattr__('_dependency_names', cls._get_dependency_names())
        location = cls._find_definition_location(inspect.stack(context=0)[1])
        super().__setattr__('definition_location', location)
        _tool_class_by_definition_location[location] = cls

    def _find_definition_location(cls, defining_frame) -> Tuple[str, Optional[str], int]:
        # Return the location, cls is defined.
        # Raises DefinitionAmbiguityError, if the location is unknown or already a class with the same metaclass
        # was defined at the same location (realpath of an existing source file and line number).
        # If the source file is a zip archive with a filename ending in '.zip', the path relative to the root
        # of the archive is also given.

        # frame relies based on best practises, correct information not guaranteed
        source_lineno = defining_frame.lineno
        if not os.path.isabs(defining_frame.filename):
            msg = (
                f"invalid tool definition: location of definition depends on current working directory\n"
                f"  | class: {cls!r}\n"
                f"  | source file: {defining_frame.filename!r}\n"
                f"  | make sure the matching module search path is an absolute path when the "
                f"defining module is imported"
            )
            raise DefinitionAmbiguityError(msg)

        source_path = os.path.realpath(defining_frame.filename)
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
                dir_path = os.path.dirname(source_path)

                ext = '.zip'
                i = dir_path.rfind(ext + os.path.sep)
                if i <= 0:
                    raise ValueError
                source_path, in_archive_path = dir_path[:i + len(ext)], source_path[i + len(ext) + 1:]

                if not os.path.isfile(source_path):
                    raise ValueError
                in_archive_path = os.path.normpath(in_archive_path)

        except Exception:
            msg = (
                f"invalid tool definition: location of definition is unknown\n"
                f"  | class: {cls!r}\n"
                f"  | define the class in a regular file or in a zip archived with '.zip'\n"
                f"  | note also the importance of upper and lower case of module search paths on "
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
            if name in _ToolMeta.OVERRIDEABLE_ATTRIBUTES:
                pass
            elif EXECUTION_PARAMETER_NAME_REGEX.match(name):
                # if overridden: must be instance of type of overridden attribute
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not isinstance(value, type(base_value)):
                        msg = (
                            f"attribute {name!r} of base class may only be overridden with a value "
                            f"which is a {type(base_value)!r}"
                        )
                        raise TypeError(msg)
            elif DEPENDENCY_NAME_REGEX.match(name):
                # noinspection PyUnresolvedReferences
                if not (isinstance(value, _ToolBase.Dependency) and isinstance(value, depend.ConcreteDependency)):
                    msg = (
                        f"the value of {name!r} must be an instance of a concrete subclass of "
                        f"'dlb.ex.Tool.Dependency'"
                    )
                    raise TypeError(msg)
                for base_class in cls.__bases__:
                    value: depend.Dependency
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not value.compatible_and_no_less_restrictive(base_value):
                        msg = (
                            f"attribute {name!r} of base class may only be overridden by "
                            f"a {type(base_value)!r} at least as restrictive"
                        )
                        raise TypeError(msg)
            else:
                msg = (
                    f"invalid class attribute name: {name!r} "
                    f"(every class attribute of a 'dlb.ex.Tool' must be named "
                    f"like 'UPPER_CASE_WORD' or 'lower_case_word)"
                )
                raise AttributeError(msg)

    def _get_dependency_names(cls) -> Tuple[str, ...]:
        dependencies = {n: getattr(cls, n) for n in dir(cls) if DEPENDENCY_NAME_REGEX.match(n)}

        def rank_of(d):
            if isinstance(d, depend.Input):
                return 0
            if isinstance(d, depend.Output):
                return 1
            return 2

        pairs = [(rank_of(d), not d.required, n) for n, d in dependencies.items() if isinstance(d, depend.Dependency)]
        pairs.sort()
        # order: input - intermediate - output, required first
        return tuple(p[-1] for p in pairs)

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
    permanent_local_id = marshal.dumps((definition_path, in_archive_path, lineno))
    if definition_path is not None:
        definition_paths.add(definition_path)

    info = ToolInfo(permanent_local_tool_id=permanent_local_id, definition_paths=definition_paths)
    _registered_info_by_tool[tool] = info

    return info


# noinspection PyCallByClass
type.__setattr__(Tool, '__module__', '.'.join(_ToolBase.__module__.split('.')[:-1]))
ut.set_module_name_to_parent_by_name(vars(), [n for n in __all__ if not 'Tool'])
