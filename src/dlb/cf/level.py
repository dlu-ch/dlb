# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Log levels for dlb.di by category."""

from .. import di

run_preparation: int = di.DEBUG + 3
run_serialization: int = di.INFO

redo_necessity_check: int = di.DEBUG + 3
redo_reason: int = di.INFO
redo_suspicious_reason: int = di.WARNING

redo_preparation: int = di.DEBUG + 5
redo_start: int = di.INFO
redo_aftermath: int = di.DEBUG + 5

helper_execution: int = di.DEBUG + 7
output_filesystem_object_replacement: int = di.INFO

run_summary: int = di.INFO

del di
