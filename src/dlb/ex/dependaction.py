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

import os
import stat
from typing import Type, Set, Optional, Sequence, Hashable
from .. import ut
from .. import fs
from . import rundb
from . import worktree
from . import depend


# this prevents actions to be exposed to the user via dependency classes
_action_by_dependency = {}  # key: registered dependency class, value: (unique id of dependency class id, action)
_dependency_class_ids: Set[int] = set()  # contains the first element of each value of _action_by_dependency


# noinspection PyMethodMayBeStatic
class Action:
    def __init__(self, dependency: depend.Dependency, name: str):
        self._dependency = dependency
        self._name = name

    @property
    def dependency(self):
        return self._dependency

    @property
    def name(self):
        return self._name

    # overwrite in subclasses
    def get_permanent_local_value_id(self, validated_values: Optional[Sequence[Hashable]]) -> bytes:
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
        return ut.to_permanent_local_bytes(validated_values)

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
        # note: *required* does _not_ affect the meaning or treatment of a the _validated_ value.
        return ut.to_permanent_local_bytes((dependency_id, d.explicit))

    # overwrite in subclass; only called for an existing filesystem object that is an explicit dependency
    def check_filesystem_object_memo(self, memo: rundb.FilesystemObjectMemo):
        raise ValueError("is not a filesystem object")

    # overwrite in subclass; only called for an existing filesystem object that is an explicit dependency
    def replace_filesystem_object(self, source: fs.Path, destination: fs.Path, context) -> bool:
        # *source* and *destination* are different managed tree paths with same *is_dir()*
        # remove *source* if successful
        # return bool is *destination* is possibly changed
        raise ValueError("is not a filesystem object that is an output dependency")


class _FilesystemObjectMixin(Action):
    def get_permanent_local_value_id(self, validated_values: Optional[Sequence[fs.Path]]) -> bytes:
        if validated_values is not None:
            validated_values = tuple(v.as_string().encode() for v in validated_values)  # avoid strings
        # note: cls does _not_ affect the meaning or treatment of a the _validated_ value.
        return ut.to_permanent_local_bytes(validated_values)

    def check_filesystem_object_memo(self, memo: rundb.FilesystemObjectMemo):
        pass


class _RegularFileMixin(_FilesystemObjectMixin):
    def check_filesystem_object_memo(self, memo: rundb.FilesystemObjectMemo):
        super().check_filesystem_object_memo(memo)
        if not stat.S_ISREG(memo.stat.mode):
            raise ValueError("filesystem object exists, but is not a regular file")


class _NonRegularFileMixin(_FilesystemObjectMixin):
    def check_filesystem_object_memo(self, memo: rundb.FilesystemObjectMemo):
        super().check_filesystem_object_memo(memo)
        if stat.S_ISREG(memo.stat.mode):
            raise ValueError("filesystem object exists, but is a regular file")
        if stat.S_ISDIR(memo.stat.mode):
            raise ValueError("filesystem object exists, but is a directory")


class _DirectoryMixin(_FilesystemObjectMixin):
    def check_filesystem_object_memo(self, memo: rundb.FilesystemObjectMemo):
        super().check_filesystem_object_memo(memo)
        if not stat.S_ISDIR(memo.stat.mode):
            raise ValueError("filesystem object exists, but is not a directory")


class RegularFileInputAction(_RegularFileMixin, Action):
    pass


class NonRegularFileInputAction(_NonRegularFileMixin, Action):
    pass


class DirectoryInputAction(_DirectoryMixin, Action):
    pass


class EnvVarInputAction(Action):

    def get_permanent_local_instance_id(self) -> bytes:
        # does _not_ depend on 'restriction'
        d = self.dependency
        return super().get_permanent_local_instance_id() + ut.to_permanent_local_bytes((d.name,))


class RegularFileOutputAction(_RegularFileMixin, _FilesystemObjectMixin, Action):

    def replace_filesystem_object(self, source: fs.Path, destination: fs.Path, context) -> bool:
        do_replace = self.dependency.replace_by_same_content

        src = str((context.root_path / source).native)
        dst = str((context.root_path / destination).native)

        if not do_replace:
            try:
                ssrc = os.lstat(src)
                sdst = os.lstat(dst)
                if stat.S_IFMT(ssrc.st_mode) != stat.S_IFMT(sdst.st_mode) or ssrc.st_size != sdst.st_size:
                    do_replace = True  # type or size differs
                else:
                    max_size = 8 * 1024  # as in filecmp.BUFSIZE
                    with open(src, 'rb') as fsrc, open(dst, 'rb') as fdst:
                        while True:
                            bsrc = fsrc.read(max_size)
                            bdst = fdst.read(max_size)
                            if bsrc != bdst:
                                do_replace = True
                                break
                            if not bsrc:
                                break  # both files are completely read without difference
            except OSError:
                do_replace = True  # e.g. if *destination* does not exist

        if not do_replace:
            os.remove(src)
            return False

        try_again = False
        try:
            os.replace(src=src, dst=dst)
        except FileNotFoundError:
            try_again = True
        if try_again:
            os.makedirs((context.root_path / destination[:-1]).native, exist_ok=True)
            os.replace(src=src, dst=dst)

        return True


class NonRegularFileOutputAction(_NonRegularFileMixin, _FilesystemObjectMixin, Action):

    def replace_filesystem_object(self, source: fs.Path, destination: fs.Path, context) -> bool:
        r = context.root_path
        src = str((r / source).native)
        dst = str((r / destination).native)

        try_again = False
        try:
            os.replace(src=src, dst=dst)
        except FileNotFoundError:
            try_again = True
        if try_again:
            os.makedirs((r / destination[:-1]).native, exist_ok=True)
            os.replace(src=src, dst=dst)

        return True


class DirectoryOutputAction(_DirectoryMixin, _FilesystemObjectMixin, Action):

    def replace_filesystem_object(self, source: fs.Path, destination: fs.Path, context) -> bool:
        r = context.root_path
        src = str((r / source).native)
        dst = str((r / destination).native)

        with context.temporary(is_dir=True) as tmp_dir:
            os.makedirs((r / destination[:-1]).native, exist_ok=True)
            worktree.remove_filesystem_object(dst, abs_empty_dir_path=tmp_dir, ignore_non_existent=True)
            os.replace(src=src, dst=dst)

        return True


class ObjectOutputAction(Action):
    pass


def register_action(dependency_id: int, dependency: Type[depend.Dependency], action: Type[Action]):
    # Registers the concrete dependency class 'dependency' and assigns it an action 'action' as well as the
    # dependency id 'dependency_id'.
    # 'dependency_id' must be an integer unique among all registered dependency class and must not change between
    # different dlb run.

    if not (issubclass(dependency, depend.Dependency) and hasattr(dependency, 'Value')):
        raise TypeError

    dependency_id = int(dependency_id)
    try:
        did, a = _action_by_dependency[dependency]
        if a is not action:
            raise ValueError(f"'dependency' is already registered with different action: {dependency!r}")
        if did != dependency_id:
            msg = f"'dependency' is already registered with different dependency id: {dependency_id}"
            raise ValueError(msg)
    except KeyError:
        if dependency_id in _dependency_class_ids:
            raise ValueError(f"'dependency_id' is already registered with different dependency") from None
        _dependency_class_ids.add(dependency_id)
        _action_by_dependency[dependency] = (dependency_id, action)


def get_action(dependency: depend.Dependency, name: str) -> Action:
    _, a = _action_by_dependency[dependency.__class__]
    return a(dependency, name)


register_action(0, depend.RegularFileInput, RegularFileInputAction)
register_action(1, depend.NonRegularFileInput, NonRegularFileInputAction)
register_action(2, depend.DirectoryInput, DirectoryInputAction)
register_action(3, depend.EnvVarInput, EnvVarInputAction)
register_action(4, depend.RegularFileOutput, RegularFileOutputAction)
register_action(5, depend.NonRegularFileOutput, NonRegularFileOutputAction)
register_action(6, depend.DirectoryOutput, DirectoryOutputAction)
register_action(7, depend.ObjectOutput, ObjectOutputAction)
