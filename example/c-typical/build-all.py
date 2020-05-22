# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file
#    python3 "$PWD"/build-all.py'   # in the directory of this file

import sys

import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.gcc
import dlb_contrib.iso6429

if sys.stderr.isatty():
    # assume terminal compliant with ISO/IEC 6429 ("VT-100 compatible")
    dlb.di.set_output_file(dlb_contrib.iso6429.MessageColorator(sys.stderr))


class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath, dlb.fs.NoSpacePath):
    pass


class CCompiler(dlb_contrib.gcc.CCompilerGcc):
    DIALECT = 'c11'


class CLinker(dlb_contrib.gcc.CLinkerGcc):
    pass


# compile and link application written in ISO/IEC 9899:2011 (C11)
with dlb.ex.Context():
    source_directory = Path('src/')
    output_directory = Path('build/out/')

    with dlb.di.Cluster('compile'), dlb.ex.Context():
        compile_results = [
            CCompiler(
                source_files=[p],
                object_files=[output_directory / p.with_appended_suffix('.o')],
                include_search_directories=[source_directory]
            ).start()
            for p in source_directory.iterdir(name_filter=r'.+\.c', is_dir=False)
        ]

    with dlb.di.Cluster('link'), dlb.ex.Context():        
        application_file = CLinker(
            object_and_archive_files=[r.object_files[0] for r in compile_results],
            linked_file=output_directory / 'application').start().linked_file

dlb.di.inform(f'application size: {application_file.native.raw.stat().st_size} B')
