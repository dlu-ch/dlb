# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

from typing import Tuple

import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.pkgconfig
import dlb_contrib.clike
import dlb_contrib.gcc


# generate source code, compile and link GTK+ application written in C
def generate_from_source(*, version_result, source_directory: dlb.fs.Path,
                         output_directory: dlb.fs.Path, application_name: str) -> Tuple[dlb.fs.Path, bool]:

    with dlb.di.Cluster('generate version file'), dlb.ex.Context():
        class GenerateVersionFile(dlb_contrib.clike.GenerateHeaderFile):
            WD_VERSION = version_result.wd_version
            PATH_COMPONENTS_TO_STRIP = len(output_directory.components)

            def write_content(self, file):
                wd_version = dlb_contrib.clike.string_literal_from_bytes(self.WD_VERSION.encode())
                file.write(f'\n')
                file.write(f'#define APPLICATION_VERSION {wd_version}\n')
                file.write(f'#define APPLICATION_VERSION_MAJOR {version_result.version_components[0]}\n')
                file.write(f'#define APPLICATION_VERSION_MINOR {version_result.version_components[1]}\n')
                file.write(f'#define APPLICATION_VERSION_MICRO {version_result.version_components[2]}\n')

        generated_source_directory = output_directory / 'gsrc/'
        GenerateVersionFile(output_file=generated_source_directory / 'Generated/Version.h').start()

    with dlb.di.Cluster('find libraries'), dlb.ex.Context():
        pkgconfig_result = dlb_contrib.pkgconfig.PkgConfig(LIBRARY_NAMES=('gtk+-3.0',)).start()

    class CCompiler(dlb_contrib.gcc.CCompilerGcc):
        DIALECT = 'c11'

    class CLinker(dlb_contrib.gcc.CLinkerGcc):
        LIBRARY_FILENAMES = pkgconfig_result.library_filenames

    with dlb.di.Cluster('compile'), dlb.ex.Context(max_parallel_redo_count=4):
        compile_results = [
            CCompiler(  # TODO run in src
                source_files=[p],
                object_files=[output_directory / p.with_appended_suffix('.o')],
                include_search_directories=(source_directory, generated_source_directory) +
                                           pkgconfig_result.include_search_directories
            ).start()
            for p in source_directory.iterdir(name_filter=r'.+\.c', is_dir=False)
        ]

    object_files = [r.object_files[0] for r in compile_results]
    with dlb.di.Cluster('link'), dlb.ex.Context():
        application_file = CLinker(
            object_and_archive_files=object_files,
            linked_file=output_directory / application_name).start().linked_file
        dlb.di.inform(f'size: {application_file.native.raw.stat().st_size} B')

    return application_file, any(compile_results)  # True if any source was compiled (redo)
