# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@userd.noreply.github.com>

"""Actions for dependency classes for tools to be used by tool instances.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = (
    'Action',
    'register_action',
    'get_action'
)

import stat
import marshal
from typing import Type, Set, Optional, Sequence, Any, Union
from .. import ut
from .. import fs
from ..fs import manip
from . import depend


# this prevents actions to be exposed to the user via dependency classes
_action_by_dependency = {}  # key: registered dependency class, value: (unique id of dependency class id, action)
_dependency_class_ids: Set[int] = set()  # contains the first element of each value of _action_by_dependency


# noinspection PyMethodMayBeStatic
class Action:
    def __init__(self, dependency: depend.Dependency):
        self._dependency = dependency
        
    @property
    def dependency(self):
        return self._dependency

    # overwrite in subclasses
    def get_permanent_local_value_id(self, validated_values: Optional[Sequence[Any]]) -> bytes:
        # Returns a short non-empty byte string as a permanent local id for this validated values of a given instance.
        #
        # 'validated_values' is None or a tuple of the validated values (regardless of self.dependency.multiplicity).
        #
        # Two instances of the same or of different dependency classes may return different permanent local value ids
        # for the same validated value.
        #
        # Two instances of the same dependency class, whose properties differ, must return different
        # permanent local value ids if the meaning of this validated values `validated_values` of a concrete dependency
        # for a running tool instance depends on the difference.
        return marshal.dumps(ut.make_fundamental(validated_values, True))

    # overwrite and prepend super().get_permanent_local_instance_id() to return value
    def get_permanent_local_instance_id(self) -> bytes:
        # Returns a short non-empty byte string as a permanent local id for this instance.
        #
        # The permanent local id is the same on every Python run as long as PLATFORM_ID remains the same
        # (at least that's the idea).
        #
        # Two instances of different dependency classes must return different permanent local instance ids.
        #
        # Two instances of the same dependency class, whose properties differ, must return different
        # permanent local instance ids if the meaning of validated value of _any_ concrete dependency
        # for a running tool instance depends on the difference.
        #
        # Raises KeyError if this class is not registered for 'self.dependency'.
        dependency_id, _ = _action_by_dependency[self._dependency.__class__]
        d = self.dependency
        # note: required and unique do _not_ affect the meaning or treatment of a the _validated_ value.
        return marshal.dumps((dependency_id, d.explicit))

    # overwrite in subclass; only called for an existing filesystem object that is an explicit dependency
    def check_filesystem_object_memo(self, memo: manip.FilesystemObjectMemo):
        raise ValueError("is not a filesystem object")


class _FilesystemObjectMixin(Action):
    def get_permanent_local_value_id(self, validated_values: Optional[Sequence[fs.Path]]) -> bytes:
        if validated_values is not None:
            validated_values = tuple(v.as_string() for v in validated_values)
        # note: cls does _not_ affect the meaning or treatment of a the _validated_ value.
        return marshal.dumps(validated_values)

    def check_filesystem_object_memo(self, memo: manip.FilesystemObjectMemo):
        pass


class _FilesystemObjectInputMixin(_FilesystemObjectMixin):
    def get_permanent_local_instance_id(self) -> bytes:
        d: Union[depend.RegularFileInput, depend.NonRegularFileInput, depend.DirectoryInput] = self.dependency
        return super().get_permanent_local_instance_id() + marshal.dumps(d.ignore_permission)


class _RegularFileMixin(_FilesystemObjectMixin):
    def check_filesystem_object_memo(self, memo: manip.FilesystemObjectMemo):
        super().check_filesystem_object_memo(memo)
        if not stat.S_ISREG(memo.stat.mode):
            raise ValueError("filesystem object exists, but is not a regular file")


class _NonRegularFileMixin(_FilesystemObjectMixin):
    def check_filesystem_object_memo(self, memo: manip.FilesystemObjectMemo):
        super().check_filesystem_object_memo(memo)
        if stat.S_ISREG(memo.stat.mode):
            raise ValueError("filesystem object exists, but is a regular file")
        if stat.S_ISDIR(memo.stat.mode):
            raise ValueError("filesystem object exists, but is a directory")


class _DirectoryMixin(_FilesystemObjectMixin):
    def check_filesystem_object_memo(self, memo: manip.FilesystemObjectMemo):
        super().check_filesystem_object_memo(memo)
        if not stat.S_ISDIR(memo.stat.mode):
            raise ValueError("filesystem object exists, but is not a directory")


class RegularFileInputAction(_RegularFileMixin, _FilesystemObjectInputMixin, Action):
    pass


class NonRegularFileInputAction(_NonRegularFileMixin, _FilesystemObjectInputMixin, Action):
    pass


class DirectoryInputAction(_DirectoryMixin, _FilesystemObjectInputMixin, Action):
    pass


class EnvVarInputAction(Action):
    pass  # does _not_ depend on 'restriction'


class RegularFileOutputAction(_RegularFileMixin, _FilesystemObjectMixin, Action):
    pass


class NonRegularFileOutputAction(_NonRegularFileMixin, _FilesystemObjectMixin, Action):
    pass


class DirectoryOutputAction(_DirectoryMixin, _FilesystemObjectMixin, Action):
    pass


def register_action(dependency_id: int, dependency: Type[depend.Dependency], action: Type[Action]):
    # Registers the dependency class 'dependency' and assigns it an action 'action' as well as the
    # dependency id 'dependency_id'.
    # 'dependency_id' must be an integer unique among all registered dependency class and must not change between
    # different dlb run.

    dependency_id = int(dependency_id)
    try:
        did, a = _action_by_dependency[dependency]
        if a is not action:
            raise ValueError(f"dependency already registered with different action: {dependency!r}")
        if did != dependency_id:
            msg = f"'dependency_id'' is already registered with different dependency: {dependency_id}"
            raise ValueError(msg)
    except KeyError:
        _dependency_class_ids.add(dependency_id)
        _action_by_dependency[dependency] = (dependency_id, action)


def get_action(dependency: depend.Dependency) -> Action:
    _, a = _action_by_dependency[dependency.__class__]
    return a(dependency)


register_action(0, depend.RegularFileInput, RegularFileInputAction)
register_action(1, depend.NonRegularFileInput, NonRegularFileInputAction)
register_action(2, depend.DirectoryInput, DirectoryInputAction)
register_action(3, depend.EnvVarInput, EnvVarInputAction)
register_action(4, depend.RegularFileOutput, RegularFileOutputAction)
register_action(5, depend.NonRegularFileOutput, NonRegularFileOutputAction)
register_action(6, depend.DirectoryOutput, DirectoryOutputAction)
