# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Dependency classes for tools.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = ['Dependency', 'InputDependency', 'OutputDependency']

from typing import Hashable, Iterable, Optional, Type, TypeVar, Tuple, Union

from .. import ut
from .. import fs
from . import _mult


V = TypeVar('V', bound=Hashable)


# noinspection PyUnresolvedReferences
class Dependency(_mult.MultiplicityHolder):
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
                raise ValueError(f'iterable must be duplicate-free but contains {v!r} more than once')
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


class InputDependency(Dependency):
    pass


class OutputDependency(Dependency):
    pass


class FilesystemObjectMixin:
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


class NonDirectoryMixin(FilesystemObjectMixin):
    def validate_single(self, value) -> fs.Path:
        value = super().validate_single(value)
        if value.is_dir():
            raise ValueError(f'directory path not valid for non-directory dependency: {value!r}')
        return value


class DirectoryMixin(FilesystemObjectMixin):
    def validate_single(self, value) -> fs.Path:
        value = super().validate_single(value)
        if not value.is_dir():
            raise ValueError(f'non-directory path not valid for directory dependency: {value!r}')
        return value


ut.set_module_name_to_parent_by_name(vars(), __all__)
