# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""dlb - a Pythonic build tool."""

from .version import __version__

# inter-dependencies of modules of this package
# (later line may depend on earlier lines):
#
#                 depends on
#
#     ut             ->
#     fs             ->
#     di             ->   ut  fs
#     cf             ->           di
#     ex             ->   ut  fs  di  cf
