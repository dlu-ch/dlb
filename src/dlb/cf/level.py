# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Log levels for dlb.di by category."""

from .. import di

RUN_PREPARATION: int = di.DEBUG + 3
RUN_SERIALIZATION: int = di.INFO

REDO_NECESSITY_CHECK: int = di.DEBUG + 3
REDO_REASON: int = di.INFO
REDO_SUSPICIOUS_REASON: int = di.WARNING

REDO_PREPARATION: int = di.DEBUG + 5
REDO_START: int = di.INFO
REDO_AFTERMATH: int = di.DEBUG + 5

HELPER_EXECUTION: int = di.DEBUG + 7

RUN_SUMMARY: int = di.INFO
