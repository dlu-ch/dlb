# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@userd.noreply.github.com>

__all__ = (
    'Action',
    'register_action',
    'get_action'
)

import marshal
import typing
from . import depend
from . import util


# this prevents actions to be exposed to the user via dependency classes
_action_by_dependency = {}


class Action:
    def __init__(self, dependency: depend.Dependency):
        self._dependency = dependency
        
    @property
    def dependency(self):
        return self._dependency

    # overwrite in subclasses
    def get_permanent_local_value_id(self, validated_value) -> bytes:
        # Returns a short byte string as a permanent local id for this validated value of a given instance.
        #
        # Two instances of the same or of different dependency classes may return different permanent local value ids
        # for the same value.
        #
        # Must return different permanent local value id for the same instance, if the value
        #
        # Two instances of the same dependency class whose properties differ, must return different
        # permanent local value ids, if the meaning or treatment of a validated value by the instance depends on
        # the difference.
        return marshal.dumps(util.make_fundamental(validated_value, True))

    # overwrite and call method of superclass in subclasses
    def get_permanent_local_instance_id(self) -> bytes:
        # Returns a short byte string as a permanent local id for this instance.
        #
        # The permanent local id is the same on every Python run as long as PLATFORM_ID remains the same
        # (at least that's the idea).
        #
        # Two instances of different dependency classes must return different permanent local instance ids.
        #
        # Two instances of the same dependency class whose properties differ, must return different
        # permanent local instance ids, if the meaning or treatment of a the validated value of concrete dependency of
        # this dependency rule depends on the difference.
        #
        # Raises KeyError if this class is not registered of the dependency.
        register_index, _ = _action_by_dependency[self._dependency.__class__]
        d = self.dependency
        # note: required and unique do _not_ affect the meaning or treatment of a the _validated_ value.
        return marshal.dumps((register_index, d.explicit))


class _FilesystemObjectMixin:
    def get_permanent_local_value_id(self, value) -> bytes:
        if value is not None:
            if self.dependency.multiplicity is None:
                value = value.as_string()
            else:
                value = tuple(v.as_string() for v in value)
        # note: cls does _not_ affect the meaning or treatment of a the _validated_ value.
        return marshal.dumps(value)


class _FilesystemObjectInputMixin(_FilesystemObjectMixin):
    def get_permanent_local_instance_id(self) -> bytes:
        d = self.dependency
        return super().get_permanent_local_instance_id() + marshal.dumps(d.ignore_permission)


class RegularFileInputAction(_FilesystemObjectInputMixin, Action):
    pass


class NonRegularFileInputAction(_FilesystemObjectInputMixin, Action):
    pass


class DirectoryInputAction(_FilesystemObjectInputMixin, Action):
    pass


class EnvVarInputAction(Action):
    pass  # does _not_ depend on 'restriction'


class RegularFileOutputAction(_FilesystemObjectMixin, Action):
    pass


class NonRegularFileOutputAction(_FilesystemObjectMixin, Action):
    pass


class DirectoryOutputAction(_FilesystemObjectMixin, Action):
    pass


def register_action(dependency: typing.Type[depend.Dependency], action: typing.Type[Action]):
    a = _action_by_dependency.get(dependency)
    if not (a is None or a is action):
        raise ValueError(f"dependency already registered with different action: {dependency!r}")
    _action_by_dependency[dependency] = (len(_action_by_dependency), action)  # assign a unique id by register order


def get_action(dependency: depend.Dependency) -> Action:
    _, a = _action_by_dependency[dependency.__class__]
    return a(dependency)


register_action(depend.RegularFileInput, RegularFileInputAction)
register_action(depend.NonRegularFileInput, NonRegularFileInputAction)
register_action(depend.DirectoryInput, DirectoryInputAction)
register_action(depend.EnvVarInput, EnvVarInputAction)
register_action(depend.RegularFileOutput, RegularFileOutputAction)
register_action(depend.NonRegularFileOutput, NonRegularFileOutputAction)
register_action(depend.DirectoryOutput, DirectoryOutputAction)
