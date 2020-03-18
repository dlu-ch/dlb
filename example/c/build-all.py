# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file.
#    python3 "$PWD"/build-all.py'   # in the directory of this file.

import sys
import os.path
assert sys.version_info >= (3, 7)
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '..', '..', 'src')))

import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib_pkgconfig
import dlb_contrib_clike
import dlb_contrib_gcc
import dlb_contrib_doxygen
import dlb_contrib_zip
import build.version_from_repo


class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath):
    pass


# compile and link application written in C
def build_application(*, version_result, source_path: Path, output_path: Path, application_name: str):
    with dlb.di.Cluster('Generate version file'), dlb.ex.Context():
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

    with dlb.di.Cluster('Find libraries'), dlb.ex.Context():
        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('gtk+-3.0',)
        pkgconfig_result = PkgConfig().run()

    class CCompiler(dlb_contrib_gcc.CCompilerGcc):
        DIALECT = 'c11'

    class CLinker(dlb_contrib_gcc.CLinkerGcc):
        LIBRARY_FILENAMES = pkgconfig_result.library_filenames

    with dlb.di.Cluster('Compile'), dlb.ex.Context(max_parallel_redo_count=4):
        compile_results = [
            CCompiler(  # TODO run in src
                source_file=p,
                object_file=output_path / p.with_appended_suffix('.o'),
                include_search_directories=(source_path, generated_source_path) +
                                           pkgconfig_result.include_search_directories
            ).run()
            for p in source_path.list(name_filter=r'.+\.c') if not p.is_dir()
        ]

    with dlb.di.Cluster('Link'), dlb.ex.Context():
        application_file = CLinker(
            object_and_archive_files=[r.object_file for r in compile_results],
            linked_file=output_path / application_name).run().linked_file
        dlb.di.inform(f'size: {application_file.native.raw.stat().st_size} B')

    return any(compile_results)


# generate zipped HTML documentation from markup in source code comments and from "free" pages
def build_documentation(*, version_result, source_path: Path, output_path: Path, application_name: str,
                        sources_changed: bool):
    with dlb.di.Cluster('Document'):

        class Doxygen(dlb_contrib_doxygen.Doxygen):
            TEXTUAL_REPLACEMENTS = {
                'project_version': f'version {version_result.wd_version}',
                'source_paths_to_strip': [str(source_path.native), str((output_path / 'gsrc/').native)]
            }

        # redo if sources_changed is True or any of the regular files in doc/doxygen/ changed
        output_directory = Doxygen(
            configuration_template_file='doc/doxygen/Doxyfile.tmpl',
            source_directories=[source_path, output_path / 'gsrc/', 'doc/doxygen/'],
            output_directory=output_path / 'doxygen/',
            source_files_to_watch=Path('doc/doxygen/').list()).run(force_redo=sources_changed).output_directory

        doc_archive_file = \
            output_path / '{}_{}.html.bzip'.format(application_name, version_result.wd_version.replace('?', '@'))
        dlb_contrib_zip.ZipDirectory(content_directory=output_directory / 'html/', archive_file=doc_archive_file).run(force_redo=True)


with dlb.ex.Context():
    application_name = 'application'
    source_path = Path('src/')
    output_path = Path('build/out/')

    version_result = build.version_from_repo.GetVersion().run()

    sources_changed = build_application(
        version_result=version_result,
        source_path=source_path,
        output_path=output_path,
        application_name=application_name)

    # build documentaton if Doxygen is installed
    if dlb.ex.Context.helper.get(dlb_contrib_doxygen.Doxygen.EXECUTABLE):
        build_documentation(
            version_result=version_result,
            source_path=source_path,
            output_path=output_path,
            application_name=application_name,
            sources_changed=sources_changed)
