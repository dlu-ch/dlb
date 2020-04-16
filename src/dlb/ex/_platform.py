# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Permanent identification of platform.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = []

import sys

from .. import version
from .. import ut

# changes whenever the platform, the Python version or the dlb version changes
PERMANENT_PLATFORM_ID = ut.to_permanent_local_bytes((
    # increase this when the information sources for this tuple change (e.g. sys.platform instead of
    # platform.platform())
    0,

    sys.platform,  # avoid platform.platform() - import of 'platform' is slow
    sys.hexversion,  # version of the language the running interpreter conforms to
    sys.implementation.name,  # name of the interpreter
    sys.implementation.hexversion,  # version of the interpreter
    version.__version__
))

# notes:
#  - 'platform' takes long to load
#  - os.uname() is not available on all platforms
