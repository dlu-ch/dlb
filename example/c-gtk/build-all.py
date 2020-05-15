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
import dlb.cf
import dlb.ex
import dlb_contrib.doxygen
import build.version_from_repo

# usage example: dlb 3>/dev/pts/<n>
try:
    dlb.di.set_output_file(open(3, 'w', buffering=1))
except OSError:  # e.g. because file descriptor 3 not opened by parent process
    pass


class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath):
    pass


# compile and link GTK+ application written in C
def build_application(*, version_result, source_directory: Path, output_directory: Path, application_name: str):
    import dlb_contrib.pkgconfig
    import dlb_contrib.clike
    import dlb_contrib.gcc

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
        GenerateVersionFile(file=generated_source_directory / 'Generated/Version.h').run()

    with dlb.di.Cluster('find libraries'), dlb.ex.Context():
        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('gtk+-3.0',)
        pkgconfig_result = PkgConfig().run()

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
            ).run()
            for p in source_directory.iterdir(name_filter=r'.+\.c', is_dir=False)
        ]

    object_files = [r.object_files[0] for r in compile_results]
    with dlb.di.Cluster('link'), dlb.ex.Context():
        application_file = CLinker(
            object_and_archive_files=object_files,
            linked_file=output_directory / application_name).run().linked_file
        dlb.di.inform(f'size: {application_file.native.raw.stat().st_size} B')

    return any(compile_results)  # True if any source was compiled (redo)


# generate zipped HTML documentation from markup in source code comments and from "free" pages
def build_documentation(*, version_result, source_directory: Path, output_directory: Path, application_name: str,
                        sources_changed: bool):
    import dlb_contrib.zip

    with dlb.di.Cluster('compile documentation'):

        class Doxygen(dlb_contrib.doxygen.Doxygen):
            TEXTUAL_REPLACEMENTS = {
                'project_version': f'version {version_result.wd_version}',
                'source_paths_to_strip': [str(source_directory.native), str((output_directory / 'gsrc/').native)]
            }

        # redo if sources_changed is True or any of the regular files in doc/doxygen/ changed
        output_directory = Doxygen(
            configuration_template_file='doc/doxygen/Doxyfile.tmpl',
            source_directories=[source_directory, output_directory / 'gsrc/', 'doc/doxygen/'],
            output_directory=output_directory / 'doxygen/',
            source_files_to_watch=Path('doc/doxygen/').list()).run(force_redo=sources_changed).output_directory

        doc_archive_file = \
            output_directory / '{}_{}.html.bzip'.format(application_name, version_result.wd_version)
        dlb_contrib.zip.ZipDirectory(content_directory=output_directory / 'html/', archive_file=doc_archive_file).run()


dlb.cf.latest_run_summary_max_count = 5

with dlb.ex.Context():
    application_name = 'application'
    source_directory = Path('src/')
    output_directory = Path('build/out/')

    version_result = build.version_from_repo.VersionQuery().run()

    sources_changed = build_application(
        version_result=version_result,
        source_directory=source_directory,
        output_directory=output_directory,
        application_name=application_name)

    # build documentaton if Doxygen is installed
    if dlb.ex.Context.helper.get(dlb_contrib.doxygen.Doxygen.EXECUTABLE):
        build_documentation(
            version_result=version_result,
            source_directory=source_directory,
            output_directory=output_directory,
            application_name=application_name,
            sources_changed=sources_changed)
