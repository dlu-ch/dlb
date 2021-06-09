# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Configuration parameters."""

import datetime
from . import level

# When > 0, a summary of the latest *latest_run_summary_max_count* dlb runs is output when a root context exits.
latest_run_summary_max_count: int = 0

# Run and dependency information older than *max_dependency_age* is removed when a root context is entered.
# 'max_dependency_age > datetime.timedelta(0)' must be True.
max_dependency_age: datetime.timedelta = datetime.timedelta(days=30)

# Default value for output files of execute_helper*(), that is used when *None* is given.
# False means: Output is suppressed by default.
# True means: Output file is inherited from the Python process by default.
execute_helper_inherits_files_by_default: bool = True

# Remove everyhing that is not an configuration parameter:
del datetime
