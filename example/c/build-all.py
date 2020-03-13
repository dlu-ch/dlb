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
import dlb_contrib_c
import dlb_contrib_c_gcc
import build.version_from_repo


class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath):
    pass


class CCompiler(dlb_contrib_c_gcc.CCompilerGcc):
    DIALECT = 'c11'


with dlb.ex.Context(find_helpers=True):

    output_path = Path('build/out/')
    output_path.native.raw.mkdir(parents=True, exist_ok=True)

    with dlb.di.Cluster('Generate version file'), dlb.ex.Context(find_helpers=True):

        version_result = build.version_from_repo.GetVersion().run()

        class GenerateVersionFile(dlb_contrib_c.GenerateHeaderFile):
            WD_VERSION = version_result.wd_version
            PATH_COMPONENTS_TO_STRIP = 1

            def write_content(self, file):
                wd_version = dlb_contrib_c.string_literal_from_bytes(self.WD_VERSION.encode())
                file.write(f'\n')
                file.write(f'#define APPLICATION_VERSION {wd_version}\n')
                file.write(f'#define APPLICATION_VERSION_MAJOR {version_result.version_components[0]}\n')
                file.write(f'#define APPLICATION_VERSION_MINOR {version_result.version_components[1]}\n')
                file.write(f'#define APPLICATION_VERSION_MICRO {version_result.version_components[2]}\n')

        generated_source_path = output_path / 'gsrc/'
        GenerateVersionFile(file=generated_source_path / 'Generated/Version.h').run()

    with dlb.di.Cluster('Compile'), dlb.ex.Context(find_helpers=True):

        source_path = dlb.fs.Path('src/')

        object_files = [
            CCompiler(
                source_file=p,
                object_file=output_path / Path(f'{p.as_string()}.o'),  # TODO add method to append to last component
                include_search_directories=[source_path, generated_source_path]  # TODO run in src
            ).run(force_redo=True).object_file  # TODO let run always return a ResultProxy
            for p in source_path.list(name_filter=r'.+\.c') if not p.is_dir()
        ]
