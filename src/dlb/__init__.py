# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""dlb - a Pythonic build tool."""

import sys
from .version import __version__, version_info
del version

assert sys.version_info >= (3, 7)
del sys

# inter-dependencies of modules of this package
# (later line may depend on earlier lines):
#
#                 depends on
#
#     ut             ->
#     di             ->   ut
#     fs             ->
#     cf             ->           di
#     ex             ->   ut  fs  di  cf
