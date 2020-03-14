# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run 'python3 -m build-all' in the directory of this file.
# TODO allow start with relative path: python3 build-all.py

import sys
import os.path
assert sys.version_info >= (3, 7)
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '..', '..', 'src')))

import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib_clike
import dlb_contrib_gcc
import build.version_from_repo


class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath):
    pass


def build_application(*, source_path: Path, output_path: Path, application_name: str):
    class CCompiler(dlb_contrib_gcc.CCompilerGcc):
        DIALECT = 'c11'

    class CLinker(dlb_contrib_gcc.CLinkerGcc):
        pass

    with dlb.di.Cluster('Generate version file'), dlb.ex.Context():
        version_result = build.version_from_repo.GetVersion().run()

        class GenerateVersionFile(dlb_contrib_clike.GenerateHeaderFile):
            WD_VERSION = version_result.wd_version
            PATH_COMPONENTS_TO_STRIP = len(output_path.components)

            def write_content(self, file):
                wd_version = dlb_contrib_clike.string_literal_from_bytes(self.WD_VERSION.encode())
                file.write(f'\n')
                file.write(f'#define APPLICATION_VERSION {wd_version}\n')
                file.write(f'#define APPLICATION_VERSION_MAJOR {version_result.version_components[0]}\n')
                file.write(f'#define APPLICATION_VERSION_MINOR {version_result.version_components[1]}\n')
                file.write(f'#define APPLICATION_VERSION_MICRO {version_result.version_components[2]}\n')

        generated_source_path = output_path / 'gsrc/'
        GenerateVersionFile(file=generated_source_path / 'Generated/Version.h').run()

    with dlb.di.Cluster('Compile'), dlb.ex.Context(max_parallel_redo_count=4):
        object_files = [
            CCompiler(
                source_file=p,
                object_file=output_path / p.with_appended_suffix('.o'),
                include_search_directories=[source_path, generated_source_path]  # TODO run in src
            ).run().object_file
            for p in source_path.list(name_filter=r'.+\.c') if not p.is_dir()
        ]

    with dlb.di.Cluster('Link'), dlb.ex.Context():
        application_file = CLinker(
            object_and_archive_files=object_files,
            linked_file=output_path / application_name).run().linked_file
        dlb.di.inform(f'size: {application_file.native.raw.stat().st_size} B')


with dlb.ex.Context():
    build_application(source_path=Path('src/'), output_path=Path('build/out/'), application_name='application')
