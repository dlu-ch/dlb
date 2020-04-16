# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

from ._error import *
from ._context import *
from ._depend import *
from ._toolrun import *
from ._tool import *
from . import input
from . import output

# inter-dependencies and import order of modules of this package
# (later line may depend on earlier lines, import import in the following order):
#
#                 depends on
#
#     _platform      ->
#     _error         ->
#     _mult          ->
#
#     _rundb         ->   _platform   _error
#     _worktree      ->               _error           _rundb
#     _aseq          ->
#     _context       ->               _error           _rundb   _worktree   _aseq
#
#     _depend        ->                        _mult
#     _dependaction  ->                                _rundb   _worktree           _context   _depend
#     _tool          ->               _error                    _worktree   _aseq   _context   _depend   _dependaction
