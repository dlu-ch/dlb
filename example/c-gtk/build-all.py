# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file
#    python3 "$PWD"/build-all.py'   # in the directory of this file

import dlb.di
import dlb.fs
import dlb.cf
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.doxygen

import build.repo
import build.application
import build.documentation
import build.helpersummary

# usage example: dlb 3>/dev/pts/<n>
try:
    dlb.di.set_output_file(open(3, 'w', buffering=1))
except OSError:  # e.g. because file descriptor 3 not opened by parent process
    pass


class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath):
    pass


dlb.cf.latest_run_summary_max_count = 5

with dlb.ex.Context():
    application_name = 'application'
    source_directory = Path('src/')
    output_directory = Path('build/out/')
    distribution_directory = Path('dist/')

    version_result = build.repo.VersionQuery().start()

    source_related_check = dlb_contrib.generic.Check(result_file=output_directory / 'result/source_related').start()

    with dlb.ex.Context():

        application_file, sources_changed = build.application.generate_from_source(
            version_result=version_result,
            source_directory=source_directory,
            output_directory=output_directory,
            application_name=application_name)

        doc_archive_file = None
        if dlb.ex.Context.helper.get(dlb_contrib.doxygen.Doxygen.EXECUTABLE):  # Doxygen installed?
            doc_archive_file = build.documentation.generate_from_source(
                version_result=version_result,
                source_directory=source_directory,
                doxygen_directory=Path('doc/doxygen/'),
                output_directory=output_directory,
                application_name=application_name,
                sources_changed=sources_changed or source_related_check)

    source_related_check.result_file.native.raw.touch()

    with dlb.di.Cluster('distribute'), dlb.ex.Context():
        files_to_distribute = [] if doc_archive_file is None else [application_file, doc_archive_file]
        dlb_contrib.generic.FileCollector(
            output_directory=distribution_directory,
            input_files=files_to_distribute
        ).start()

    build.helpersummary.summarize_context()
