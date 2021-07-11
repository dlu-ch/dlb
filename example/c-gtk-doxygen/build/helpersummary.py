# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.pkgconfig
import dlb_contrib.gcc
import dlb_contrib.doxygen
from . import repo


# list used executables with version
def summarize_context():
    version_parameters_by_executable = {
        tool.EXECUTABLE: tool.VERSION_PARAMETERS
        for tool in [
            repo.VersionQuery,
            dlb_contrib.pkgconfig.PkgConfig,
            dlb_contrib.gcc.CCompilerGcc,
            dlb_contrib.gcc.CLinkerGcc,
            dlb_contrib.doxygen.Doxygen
        ]
        if dlb.fs.Path(tool.EXECUTABLE) in dlb.ex.Context.active.helper
    }

    version_by_path = dlb_contrib.generic.VersionQuery(
        VERSION_PARAMETERS_BY_EXECUTABLE=version_parameters_by_executable
    ).start().version_by_path

    executable_lines = [
        f'    {k.as_string()!r}: \t{v.as_string()!r} \t{version_by_path[v] if v in version_by_path else "?"}'
        for k, v in sorted(dlb.ex.Context.active.helper.items()) if not k.is_dir()
    ]
    dlb.di.inform('\n'.join(['used executables:'] + executable_lines))
