# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Dependency classes for tools.
This is an implementation detail - do not import it unless you know what you are doing."""

import re
import dataclasses
import copy
from typing import Pattern, TypeVar, Type, Optional, Iterable, Any, Dict, Hashable, Union, Tuple
from .. import fs
from . import mult


V = TypeVar('V', bound=Hashable)


# noinspection PyUnresolvedReferences
class Dependency(mult.MultiplicityHolder):
    # Each instance d represents a dependency role.
    # The return value of d.validate() is a concrete dependency, if d.multiplicity is None and
    # a tuple of concrete dependencies otherwise.

    def __init__(self, *, required: bool = True, explicit: bool = True):
        super().__init__()
        self._required = bool(required)  # not checked by validate(), only for the caller
        self._explicit = bool(explicit)  # not checked by validate(), only for the caller

    @property
    def required(self) -> bool:
        return self._required

    @property
    def explicit(self) -> bool:
        return self._explicit

    def compatible_and_no_less_restrictive(self, other) -> bool:
        if not isinstance(self, other.__class__):
            return False

        if (self.multiplicity is None) != (other.multiplicity is None):
            return False

        if self.multiplicity is not None:
            ss = self.multiplicity.as_slice
            so = other.multiplicity.as_slice
            if ss.step != so.step or ss.start < so.start:
                return False

            if ss.stop is None:
                if so.stop is not None:
                    return False
            else:
                if so.stop is not None and ss.stop > so.stop:
                    return False

        if other.required and not self.required:
            return False
        if self.explicit != other.explicit:
            return False

        return True

    # overwrite in base classes
    def validate_single(self, value: Optional[Hashable]) -> Hashable:
        if value is None:
            raise TypeError("'value' must not be None")
        return value

    # final
    def validate(self, value) -> Optional[Union[V, Tuple[V, ...]]]:
        if not hasattr(self, 'Value'):
            msg = (
                f"{self.__class__!r} is an abstract dependency class\n"
                f"  | use one of its documented subclasses instead"
            )
            raise NotImplementedError(msg)

        m = self.multiplicity

        if m is None:
            return self.validate_single(value)

        if value is None:
            raise TypeError("'value' must not be None")

        if m is not None and isinstance(value, (bytes, str)):  # avoid iterator over characters by mistake
            raise TypeError("since dependency has a multiplicity, value must be iterable (other than 'str' or 'bytes')")

        values = []

        # noinspection PyTypeChecker
        for v in value:
            v = self.validate_single(v)
            if v in values:
                raise ValueError(f'iterable must be duplicate-free, but contains {v!r} more than once')
            values.append(v)

        n = len(values)
        if n not in m:
            msg = f'value has {n} members, which is not accepted according to the specified multiplicity {m}'
            raise ValueError(msg)

        return tuple(values)

    def tuple_from_value(self, value: Union[None, V, Iterable[V]]) -> Tuple[V, ...]:
        if value is None:
            return ()
        if self.multiplicity is None:
            return value,
        return tuple(v for v in value)


class Input(Dependency):
    pass


class Output(Dependency):
    pass


class _FilesystemObjectMixin:
    Value = fs.Path

    def __init__(self, *, cls: Type[fs.Path] = fs.Path, **kwargs):
        super().__init__(**kwargs)
        if not (isinstance(cls, type) and issubclass(cls, fs.Path)):
            raise TypeError("'cls' is not a subclass of 'dlb.fs.Path'")
        self._path_cls = cls

    @property
    def cls(self) -> Type[fs.Path]:
        return self._path_cls

    def compatible_and_no_less_restrictive(self, other) -> bool:
        if not super().compatible_and_no_less_restrictive(other):
            return False

        return issubclass(self.cls, other.cls)

    def validate_single(self, value) -> fs.Path:
        value = super().validate_single(value)
        # noinspection PyTypeChecker
        return self._path_cls(value)


class _NonDirectoryMixin(_FilesystemObjectMixin):
    def validate_single(self, value) -> fs.Path:
        value = super().validate_single(value)
        if value.is_dir():
            raise ValueError(f'directory path not valid for non-directory dependency: {value!r}')
        return value


class _DirectoryMixin(_FilesystemObjectMixin):
    def validate_single(self, value) -> fs.Path:
        value = super().validate_single(value)
        if not value.is_dir():
            raise ValueError(f'non-directory path not valid for directory dependency: {value!r}')
        return value


class RegularFileInput(_NonDirectoryMixin, Input):
    pass


class NonRegularFileInput(_NonDirectoryMixin, Input):
    pass


class DirectoryInput(_DirectoryMixin, Input):
    pass


class RegularFileOutput(_NonDirectoryMixin, Output):

    def __init__(self, *, replace_by_same_content: bool = True, **kwargs):
        super().__init__(**kwargs)
        self._replace_by_same_content = bool(replace_by_same_content)  # ignore in compatible_and_no_less_restrictive()

    @property
    def replace_by_same_content(self):
        return self._replace_by_same_content


class NonRegularFileOutput(_NonDirectoryMixin, Output):
    pass


class DirectoryOutput(_DirectoryMixin, Output):
    pass


class EnvVarInput(Input):
    @dataclasses.dataclass(frozen=True, eq=True)
    class Value:
        name: str
        raw: str
        groups: Dict[str, str]

    def __init__(self, *, name: str, restriction: Union[str, Pattern], example: str, **kwargs):
        super().__init__(**kwargs)

        if not isinstance(name, str):
            raise TypeError("'name' must be a str")
        if not name:
            raise ValueError("'name' must not be empty")

        if isinstance(restriction, str):
            restriction = re.compile(restriction)
        if not isinstance(restriction, Pattern):
            raise TypeError("'restriction' must be regular expression (compiled or str)")
        if not isinstance(example, str):
            raise TypeError("'example' must be a str")

        if not restriction.fullmatch(example):
            raise ValueError(f"'example' is invalid with respect to 'restriction': {example!r}")

        if self.multiplicity is not None:
            raise ValueError("must not have a multiplicity")

        self._name = name
        self._restriction: Pattern = restriction
        self._example = example

    @property
    def name(self) -> str:
        return self._name

    @property
    def restriction(self) -> Pattern:
        return self._restriction

    @property
    def example(self) -> str:
        return self._example

    def compatible_and_no_less_restrictive(self, other) -> bool:
        if not super().compatible_and_no_less_restrictive(other):
            return False

        return self.name == other.name and self.restriction == other.restriction  # ignore example

    def validate_single(self, value) -> 'EnvVarInput.Value':
        # value is used to defined the content of a (future) environment variable
        value = super().validate_single(value)

        if not isinstance(value, str):
            raise TypeError("'value' must be a str")

        m = self._restriction.fullmatch(value)
        if not m:
            raise ValueError(f"value is invalid with respect to restriction: {value!r}")

        # noinspection PyCallByClass
        return EnvVarInput.Value(name=self.name, raw=value, groups=m.groupdict())


class ObjectOutput(Output):
    Value = Any  # except None and NotImplemented

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.explicit:
            raise ValueError("must not be explicit")

    def validate_single(self, value) -> Any:
        value = super().validate_single(value)
        if value is NotImplemented:
            raise ValueError(f"value is invalid: {value!r}")
        return copy.deepcopy(value)


def _inject_into(owner, owner_name, owner_module):
    def _inject_nested_class_into(parent, cls, name, owner_qualname=None):
        setattr(parent, name, cls)
        cls.__module__ = owner_module
        cls.__name__ = name
        if owner_qualname is None:
            owner_qualname = parent.__qualname__
        cls.__qualname__ = owner_qualname + '.' + name

    _inject_nested_class_into(owner, Dependency, 'Dependency', owner_name)

    _inject_nested_class_into(owner, Input, 'Input', owner_name)
    _inject_nested_class_into(owner, Output, 'Output', owner_name)

    _inject_nested_class_into(owner.Input, RegularFileInput, 'RegularFile')
    _inject_nested_class_into(owner.Input, NonRegularFileInput, 'NonRegularFile')
    _inject_nested_class_into(owner.Input, DirectoryInput, 'Directory')
    _inject_nested_class_into(owner.Input, EnvVarInput, 'EnvVar')

    _inject_nested_class_into(owner.Output, RegularFileOutput, 'RegularFile')
    _inject_nested_class_into(owner.Output, NonRegularFileOutput, 'NonRegularFile')
    _inject_nested_class_into(owner.Output, DirectoryOutput, 'Directory')
    _inject_nested_class_into(owner.Output, ObjectOutput, 'Object')
