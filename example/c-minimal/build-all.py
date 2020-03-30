# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file.
#    python3 "$PWD"/build-all.py'   # in the directory of this file.

import dlb.fs
import dlb.ex
import dlb_contrib.gcc


# compile and link application written in C
with dlb.ex.Context():
    source_path = dlb.fs.Path('src/')
    output_path = dlb.fs.Path('build/out/')

    compile_results = [
        dlb_contrib.gcc.CCompilerGcc(
            source_file=p,
            object_file=output_path / p.with_appended_suffix('.o'),
            include_search_directories=[source_path]
        ).run()
        for p in source_path.list(name_filter=r'.+\.c') if not p.is_dir()
    ]

    dlb_contrib.gcc.CLinkerGcc(
        object_and_archive_files=[r.object_file for r in compile_results],
        linked_file=output_path / 'application').run()
