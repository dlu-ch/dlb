# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Output dependency classes for tools."""

import copy
from typing import Any

from . import _depend


class RegularFile(_depend.NonDirectoryMixin, _depend.OutputDependency):

    def __init__(self, *, replace_by_same_content: bool = True, **kwargs):
        super().__init__(**kwargs)
        self._replace_by_same_content = bool(replace_by_same_content)  # ignore in compatible_and_no_less_restrictive()

    @property
    def replace_by_same_content(self):
        return self._replace_by_same_content


class NonRegularFile(_depend.NonDirectoryMixin, _depend.OutputDependency):
    pass


class Directory(_depend.DirectoryMixin, _depend.OutputDependency):
    pass


class Object(_depend.OutputDependency):
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
