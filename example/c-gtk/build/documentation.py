# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.zip
#

# generate zipped HTML documentation from markup in source code comments and from "free" pages
def generate_from_source(*, version_result, source_directory: dlb.fs.Path,
                         doxygen_directory: dlb.fs.Path,
                         output_directory: dlb.fs.Path,
                         application_name: str, sources_changed: bool) -> dlb.fs.Path:

    with dlb.di.Cluster('compile documentation'):

        class Doxygen(dlb_contrib.doxygen.Doxygen):
            TEXTUAL_REPLACEMENTS = {
                'project_version': f'version {version_result.wd_version}',
                'source_paths_to_strip': [str(source_directory.native), str((output_directory / 'gsrc/').native)]
            }

        # redo if sources_changed is True or any of the regular files in doc/doxygen/ changed
        output_directory = Doxygen(
            configuration_template_file=doxygen_directory / 'Doxyfile.tmpl',
            source_directories=[source_directory, output_directory / 'gsrc/', doxygen_directory],
            output_directory=output_directory / 'doxygen/',
            source_files_to_watch=doxygen_directory.list()).start(force_redo=sources_changed).output_directory

        doc_archive_file = \
            output_directory / '{}_{}.html.bzip'.format(application_name, version_result.wd_version)
        dlb_contrib.zip.ZipDirectory(content_directory=output_directory / 'html/',
                                     archive_file=doc_archive_file).start()
    return doc_archive_file
