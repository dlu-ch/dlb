# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Input dependency classes for tools."""

import re
import dataclasses
from typing import Dict, Pattern, Union
from . import _depend


class RegularFile(_depend.NonDirectoryMixin, _depend.InputDependency):
    pass


class NonRegularFile(_depend.NonDirectoryMixin, _depend.InputDependency):
    pass


class Directory(_depend.DirectoryMixin, _depend.InputDependency):
    pass


class EnvVar(_depend.InputDependency):
    @dataclasses.dataclass(frozen=True, eq=True)
    class Value:
        name: str
        raw: str
        groups: Dict[str, str]

    def __init__(self, *, name: str, pattern: Union[str, Pattern], example: str, **kwargs):
        super().__init__(**kwargs)

        if not isinstance(name, str):
            raise TypeError("'name' must be a str")
        if not name:
            raise ValueError("'name' must not be empty")

        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        if not isinstance(pattern, Pattern):
            raise TypeError("'pattern' must be regular expression (compiled or str)")
        if not isinstance(example, str):
            raise TypeError("'example' must be a str")

        if not pattern.fullmatch(example):
            raise ValueError(f"'example' is not matched by 'pattern': {example!r}")

        if self.multiplicity is not None:
            raise ValueError("must not have a multiplicity")

        self._name = name
        self._pattern: Pattern = pattern
        self._example = example

    @property
    def name(self) -> str:
        return self._name

    @property
    def pattern(self) -> Pattern:
        return self._pattern

    @property
    def example(self) -> str:
        return self._example

    def compatible_and_no_less_restrictive(self, other) -> bool:
        if not super().compatible_and_no_less_restrictive(other):
            return False

        return self.name == other.name and self.pattern == other.pattern  # ignore example

    def validate_single(self, value) -> 'EnvVar.Value':
        # value is used to defined the content of a (future) environment variable
        value = super().validate_single(value)

        if not isinstance(value, str):
            raise TypeError("'value' must be a str")

        m = self._pattern.fullmatch(value)
        if not m:
            raise ValueError(f"value {value!r} is not matched by validation pattern {self._pattern.pattern!r}")

        # noinspection PyCallByClass
        return EnvVar.Value(name=self.name, raw=value, groups=m.groupdict())
