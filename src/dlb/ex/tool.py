# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Dependency-aware tool execution."""

__all__ = ('Tool', 'DefinitionAmbiguityError', 'DependencyRoleAssignmentError', 'DependencyCheckError')

import sys
import re
import os
import stat
import collections
import hashlib
import typing
import logging
import inspect
import marshal
from .. import fs
from ..fs import manip
from .. import di
from . import util
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

RESERVED_NAME_REGEX = re.compile('^__[^_].*[^_]?__$')
assert RESERVED_NAME_REGEX.match('__init__')
assert not RESERVED_NAME_REGEX.match('__init')


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


ToolInfo = collections.namedtuple('ToolInfo', ('permanent_local_tool_id', 'definition_paths'))


def _get_memo_for_fs_input_dependency(name: str, path: fs.Path,
                                      memo_by_encoded_path: typing.Dict[str, manip.FilesystemObjectMemo],
                                      context: context_.Context) -> typing.Tuple[str, manip.FilesystemObjectMemo]:
    # TODO document
    try:

        try:
            path = context.managed_tree_path_of(path, existing=False, collapsable=False)
        except manip.PathNormalizationError as e:
            if e.oserror is not None:
                raise e.oserror
            msg = (
                f"input dependency {name!r} contains a path that is not a managed tree path: "
                f"{path.as_string()!r}\n"
                f"  | reason: {util.exception_to_line(e)}"
            )
            raise DependencyCheckError(msg) from None

        encoded_path = rundb.encode_path(path)
        memo = memo_by_encoded_path.get(encoded_path)

        if memo is None:
            # may raise OSError except FileNotFoundError:
            memo, _ = manip.read_filesystem_object_memo(context.root_path / path)
        if memo.stat is None:
            raise FileNotFoundError

    except FileNotFoundError:
        msg = (
            f"input dependency {name!r} contains a path of an "
            f"non-existing filesystem object: {path.as_string()!r}"
        )
        raise DependencyCheckError(msg) from None

    except OSError as e:
        msg = (
            f"input dependency {name!r} contains a path of an "
            f"inaccessible filesystem object: {path.as_string()!r}\n"
            f"  | reason: {util.exception_to_line(e)}"
        )
        raise DependencyCheckError(msg) from None

    return encoded_path, memo


# TODO test
def _get_memo_for_fs_input_dependency_from_rundb(encoded_path: str, last_encoded_memo: typing.Optional[bytes],
                                                 needs_redo: bool, context: context_.Context):
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
            # may raise OSError except FileNotFoundError:
            path = context.managed_tree_path_of(path, existing=False, collapsable=False)
            memo, _ = manip.read_filesystem_object_memo(context.root_path / path)
        except manip.PathNormalizationError as e:
            if e.oserror is None:
                raise

            if not isinstance(e.oserror, FileNotFoundError):
                raise e.oserror from None

            did_not_exist_before_last_redo = False
            try:
                did_not_exist_before_last_redo = \
                    last_encoded_memo is None or rundb.decode_encoded_fsobject_memo(last_encoded_memo).stat is None
            except ValueError:
                pass

            # ignore if did not exist according to valid 'encoded_memo'
            if not did_not_exist_before_last_redo:
                raise e.oserror from None

        if last_encoded_memo is None:  # TODO is this the right place?
            if not needs_redo:
                di.inform(f"redo necessary because potentially modified by output dependency: {path.as_string()!r}",
                          level=logging.WARNING)
                needs_redo = True

    except (ValueError, OSError):
        if not needs_redo:
            msg = (
                f"redo necessary because of inexisting or inaccessible "
                f"filesystem object: {path.as_string()!r}"
            )
            di.inform(msg, level=logging.INFO)
            needs_redo = True  # comparision not possible -> redo

    return memo, needs_redo  # memo.state may be None


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
                validated_value = role.validate(value, None)

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
                    action = dependaction.get_action(role)
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
    # TODO split into smaller parts
    # TODO test all execution paths
    # TODO analyze code coverage of tests
    def run(self):
        dependency_info = tuple(
            (n, dependaction.get_action(getattr(self.__class__, n)))
            for n in self.__class__._dependency_names
        )

        # noinspection PyTypeChecker
        context: context_.Context = context_.Context.active
        db = context_._get_rundb()

        needs_redo = False

        with di.Cluster('register tool instance', with_time=True, is_progress=True):
            tool_info = get_and_register_tool_info(self.__class__)
            tool_instance_dbid = db.get_and_register_tool_instance_dbid(
                tool_info.permanent_local_tool_id,
                self.fingerprint)
            di.inform(f"tool instance dbid is {tool_instance_dbid!r}")

        memo_by_encoded_path = {}

        with di.Cluster('read and check state of filesystem objects that are explicit input dependencies',
                        with_time=True, is_progress=True):

            for name, action in dependency_info:
                # read memo of each filesystem object of a explicit input dependency in a reproducible order
                if not (action.dependency.explicit and isinstance(action.dependency, depend.Input) and
                        isinstance(action.dependency, depend.FilesystemObject)):
                    continue
                with di.Cluster(f"dependency role {name!r}", is_progress=True):
                    # all elements of validated_value_tuple are dlb.fs.Path
                    validated_value_tuple = action.dependency.tuple_from_value(getattr(self, name))
                    checked_encoded_path = set()
                    for p in validated_value_tuple:
                        encoded_path, memo = _get_memo_for_fs_input_dependency(name, p, memo_by_encoded_path, context)
                        if encoded_path not in checked_encoded_path:  # check exactly once
                            action.check_filesystem_object_memo(memo)  # raise exception if memo is not as expected
                            checked_encoded_path.add(encoded_path)
                            memo_by_encoded_path[encoded_path] = memo
                            assert memo.stat is not None

            with di.Cluster(f"tool definition files", is_progress=True):
                # treat all files used for definition of self.__class__ like explicit input dependencies if they
                # have a managed tree path.
                definition_file_count = 0
                for p in tool_info.definition_paths:
                    try:
                        encoded_path, memo = _get_memo_for_fs_input_dependency(
                            None, fs.Path(p), memo_by_encoded_path, context)  # TODO fix type and exceptions
                        definition_file_count += 1
                        memo_by_encoded_path[encoded_path] = memo
                        assert memo.stat is not None
                    except (ValueError, DependencyCheckError):
                        # silently ignore all definition files not in managed tree
                        pass
                di.inform(f"added {definition_file_count} files as input dependencies")

        with di.Cluster('clear filesystem objects that are explict output dependencies',
                        with_time=True, is_progress=True):
            for name, action in dependency_info:
                # read memo of each filesystem object of a explicit input dependency in a reproducible order
                if not (action.dependency.explicit and isinstance(action.dependency, depend.Output) and
                        isinstance(action.dependency, depend.FilesystemObject)):
                    continue

                # all elements of validated_value_tuple are dlb.fs.Path
                validated_value_tuple = action.dependency.tuple_from_value(getattr(self, name))
                for p in validated_value_tuple:
                    encoded_path = rundb.encode_path(p)  # Exceptions ???
                    db.declare_fsobject_input_as_modified(encoded_path)

        with di.Cluster('read state of filesystem objects before last redo from run-database',
                        with_time=True, is_progress=True):
            inputs_from_last_redo = db.get_fsobject_inputs(tool_instance_dbid)

        encoded_paths_of_explicit_input_dependencies = set(memo_by_encoded_path.keys())

        with di.Cluster('read and check state of filesystem objects that are non-explicit '
                        'input dependencies of the last redo', is_progress=True):
            for encoded_path, (is_explicit, last_encoded_memo) in inputs_from_last_redo.items():
                if not is_explicit and encoded_path not in memo_by_encoded_path:
                    memo, needs_redo = _get_memo_for_fs_input_dependency_from_rundb(
                        encoded_path, last_encoded_memo, needs_redo, context)
                    memo_by_encoded_path[encoded_path] = memo  # memo.state may be None

        # 'memo_by_encoded_path' contains a current memo for every filesystem object in the managed tree that
        # is an explicit input dependency of this call of 'run()' or an non-explicit input dependency of the
        # last successful redo of the same tool instance according to the run-database

        if not needs_redo and memo_by_encoded_path and not inputs_from_last_redo:
            # there _are_ input dependencies
            msg = f"redo necessary because state of all input dependencies before the last successful redo is unknown"
            di.inform(msg)
            needs_redo = True

        if not needs_redo:
            with di.Cluster('compare state of filesystem objects with state that are non-explicit '
                            'input dependencies of the last redo', with_time=True, is_progress=True):

                # use encoded_paths_of_explicit_input_dependencies ???
                encoded_path = None

                for encoded_path, memo in memo_by_encoded_path.items():  # sorting not necessary for repeatability
                    is_explicit, last_encoded_memo = inputs_from_last_redo.get(encoded_path, (True, None))
                    assert memo.stat is not None or not is_explicit

                    if last_encoded_memo is None:
                        # state before last successful redo is unknown (maybe because it was declared as modified)
                        needs_redo = True
                        break

                    try:
                        last_memo = rundb.decode_encoded_fsobject_memo(last_encoded_memo)
                    except ValueError:
                        # state before last successful redo is unknown
                        needs_redo = True
                        break

                    if encoded_path in encoded_paths_of_explicit_input_dependencies:
                        assert memo.stat is not None
                        if last_memo.stat is None:
                            needs_redo = True
                            break
                    elif (memo.stat is None) != (last_memo.stat is None):
                        # existence has changed
                        needs_redo = True
                        break
                    elif memo.stat is None:
                        continue

                    assert memo.stat is not None
                    assert last_memo.stat is not None

                    if stat.S_IFMT(memo.stat.mode) != stat.S_IFMT(last_memo.stat.mode):
                        # type of filesystem object has changed
                        needs_redo = True
                        break

                    if stat.S_ISLNK(memo.stat.mode) and memo.symlink_target != last_memo.symlink_target:
                        # symlink target has changed
                        needs_redo = True
                        break

                    if (memo.stat.size, memo.stat.mtime_ns) != (last_memo.stat.size, last_memo.stat.mtime_ns):
                        # size or mtime has changed
                        needs_redo = True
                        break

                    if (memo.stat.mode, memo.stat.uid, memo.stat.gid) != \
                            (last_memo.stat.mode, last_memo.stat.size, last_memo.stat.mtime_ns):
                        # TODO
                        # permissions have changed
                        needs_redo = True
                        break

                if encoded_path is not None:
                    path = rundb.decode_encoded_path(encoded_path)
                    msg = f"redo necessary because state ???: {path.as_string()!r}"
                    di.inform(msg)

        db.commit()

        result = None
        if needs_redo:
            with di.Cluster('redo', with_time=True, is_progress=True):
                result = self.redo()

        # redo was successful, so save the state before the redo to the run-database

        info_by_by_fsobject_dbid = {
            encoded_path: (True, rundb.encode_fsobject_memo(memo))
            for encoded_path, memo in memo_by_encoded_path.items()
        }
        db.replace_fsobject_inputs(tool_instance_dbid, info_by_by_fsobject_dbid)

        db.commit()

        return result

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
    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)

        # prevent attributes of _ToolBase from being overridden
        protected_attrs = (set(_ToolBase.__dict__.keys()) - {'__doc__', '__module__'} | {'__new__'})
        attrs = set(cls.__dict__) & protected_attrs
        if attrs:
            raise AttributeError("must not be overridden in a 'dlb.ex.Tool': {}".format(repr(sorted(attrs)[0])))

        cls.check_own_attributes()
        super().__setattr__('_dependency_names', cls._get_dependency_names())
        location = cls._find_definition_location(inspect.stack(context=0)[1])
        super().__setattr__('definition_location', location)
        _tool_class_by_definition_location[location] = cls

    def _find_definition_location(cls, defining_frame) -> typing.Tuple[str, typing.Optional[str], int]:
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
            if name in ('redo',):
                pass
            elif RESERVED_NAME_REGEX.match(name):
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

    def _get_dependency_names(cls) -> typing.Tuple[str, ...]:
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


class Tool(_ToolBase, metaclass=_ToolMeta):
    pass


def get_and_register_tool_info(tool: typing.Type) -> ToolInfo:
    # Return a ToolInfo with a permanent local id of tool and a set of all source file in the managed tree in
    # which the class or one of its baseclass of type `base_cls` is defined.
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

    definition_path, in_archive_path, lineno = tool.definition_location
    permanent_local_id = marshal.dumps((definition_path, in_archive_path, lineno))
    if definition_path is not None:
        definition_paths.add(definition_path)

    info = ToolInfo(permanent_local_tool_id=permanent_local_id, definition_paths=definition_paths)
    _registered_info_by_tool[tool] = info

    return info


# noinspection PyCallByClass
type.__setattr__(Tool, '__module__', '.'.join(_ToolBase.__module__.split('.')[:-1]))
util.set_module_name_to_parent_by_name(vars(), [n for n in __all__ if not 'Tool'])
