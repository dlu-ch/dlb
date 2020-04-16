# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Exception classes for dlb.ex.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = [
    'NoWorkingTreeError',
    'ManagementTreeError',
    'WorkingTreeTimeError',
    'NotRunningError',
    'ContextNestingError',
    'ContextModificationError',
    'WorkingTreePathError',
    'DefinitionAmbiguityError',
    'DependencyError',
    'ExecutionParameterError',
    'RedoError',
    'HelperExecutionError',
    'DatabaseError'
]

from typing import Optional
from .. import ut


class NoWorkingTreeError(Exception):
    pass


class ManagementTreeError(Exception):
    pass


class WorkingTreeTimeError(Exception):
    pass


class NotRunningError(Exception):
    pass


class ContextNestingError(Exception):
    pass


class ContextModificationError(Exception):
    pass


class WorkingTreePathError(ValueError):
    def __init__(self, *args, oserror: Optional[OSError] = None):
        super().__init__(*args)
        self.oserror = oserror


class DefinitionAmbiguityError(SyntaxError):
    pass


class DependencyError(ValueError):
    pass


class ExecutionParameterError(Exception):
    pass


class RedoError(Exception):
    pass


class HelperExecutionError(Exception):
    pass


class DatabaseError(Exception):
    pass


ut.set_module_name_to_parent_by_name(vars(), __all__)
