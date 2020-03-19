# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Log levels for dlb.di by category."""

from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG

RUN_PREPARATION: int = DEBUG + 3
RUN_SERIALIZATION: int = INFO

REDO_NECESSITY_CHECK: int = DEBUG + 3
REDO_REASON: int = INFO
REDO_SUSPICIOUS_REASON: int = WARNING

REDO_PREPARATION: int = DEBUG + 5
REDO_START: int = INFO
REDO_AFTERMATH: int = DEBUG + 5

HELPER_EXECUTION: int = DEBUG + 7

RUN_SUMMARY: int = INFO
