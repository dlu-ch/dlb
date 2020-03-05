# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Permanent identification of platform.
This is an implementation detail - do not import it unless you know what you are doing."""

import sys
import platform
import sqlite3
from .. import version
from .. import ut
assert sys.version_info >= (3, 7)

# changes whenever the platform, the Python version or the dlb version changes
PERMANENT_PLATFORM_ID = ut.to_permanent_local_bytes((
    platform.platform(),
    sys.hexversion,
    version.__version__,
    sqlite3.sqlite_version_info  # the SQLite library, not the Python module
))
