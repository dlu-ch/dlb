# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file
#    python3 "$PWD"/build-all.py'   # in the directory of this file

import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.partition
import dlb_contrib.gcc


# compile and link application written in C
with dlb.ex.Context():
    source_directory = dlb.fs.Path('src/')
    output_directory = dlb.fs.Path('build/out/')

    # group multiple source files for the same compiler tool instance the reduce time and space for dependency checking
    source_files = source_directory.list(name_filter=r'.+\.c', is_dir=False)
    source_file_groups = dlb_contrib.partition.by_working_tree_path(source_files,
                                                                    number_of_groups=len(source_files) // 10)
    del source_files
    source_file_groups = dlb_contrib.partition.split_longer(source_file_groups, max_length=15)
    # source_file_groups contains lists of approx. 10 (max. 15) source file paths each

    ns = [len(g) for g in source_file_groups]
    dlb.di.inform(f'{len(source_file_groups)} source file groups with {min(ns)} to {max(ns)} source files')
    del ns

    with dlb.ex.Context(max_parallel_redo_count=4):
        compile_results = [
            dlb_contrib.gcc.CCompilerGcc(
                source_files=g,
                object_files=[output_directory / p.with_appended_suffix('.o') for p in g],
                include_search_directories=[source_directory]
            ).run()
            for g in source_file_groups
        ]

    object_file_groups = [r.object_files for r in compile_results]
    dlb_contrib.gcc.CLinkerGcc(
        object_and_archive_files=[o for g in object_file_groups for o in g],
        linked_file=output_directory / 'application').run()
