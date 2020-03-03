# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""The language C and its tools."""

import sys
import dlb.ex
assert sys.version_info >= (3, 7)


# noinspection PyAbstractClass
class CCompiler(dlb.ex.Tool):

    source_file = dlb.ex.Tool.Input.RegularFile()
    object_file = dlb.ex.Tool.Output.RegularFile()

    # tuple of paths of directories that are to be searched for include files in addition to the system include files
    include_search_directories = dlb.ex.Tool.Input.Directory[:](required=False)

    # paths of all files in the managed tree directly or indirectly included by *source_file*
    included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)
