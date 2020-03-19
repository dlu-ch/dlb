# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""dlb - a Pythonic build tool."""

from . import level

# When > 0, a summary of the latest *lastest_run_summary_max_count* dlb runs is output when a root context exits.
lastest_run_summary_max_count: int = 0
