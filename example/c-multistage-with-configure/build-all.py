# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file
#    python3 "$PWD"/build-all.py    # in the directory of this file

import sys

import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.filesystem
import dlb_contrib.gcc
import dlb_contrib.exctrace
import dlb_contrib.iso6429


dlb_contrib.exctrace.enable_compact_with_cwd()
if sys.stderr.isatty():
    # assume terminal compliant with ISO/IEC 6429 ("VT-100 compatible")
    dlb.di.set_output_file(dlb_contrib.iso6429.MessageColorator(sys.stderr))


class CCompiler(dlb_contrib.gcc.CCompilerGcc):
    DIALECT = 'gnu99'  # 'c99' disables POSIX extensions


class CLinker(dlb_contrib.gcc.CLinkerGcc):
    pass


source_directory = dlb.fs.Path('src/')
output_directory = dlb.fs.Path('build/out/')
generated_source_directory = output_directory / 'gsrc/'
dist_directory = dlb.fs.Path('dist/')


def configure():
    with dlb.di.Cluster('configure'), dlb.ex.Context():
        configuration_file = generated_source_directory / 'Generated/Configuration.h'

        if dlb_contrib.generic.Check(output_files=[configuration_file]).start():
            has_8bit_byte = CCompiler.check_constant_expression(
                '(unsigned char) 255 == 255 && (unsigned char) 256 == 0', by_preprocessor=False)
            # C99 requires 'char' of at least 7 bit per "byte" where 1 "byte" is the size of 'char'
            assert has_8bit_byte, 'need compiler wich a "byte" of exactly 8 bit'

            has_twos_complement_representation = CCompiler.check_constant_expression(
                '(unsigned char) -1 == 255u', by_preprocessor=False)
            assert has_twos_complement_representation, \
                "need compiler with two's complement representation of signed integers"

            # C99 (ISO/IEC 9899:1999)
            #   provides '#include <time.h>'
            # POSIX (https://pubs.opengroup.org/onlinepubs/009695399/basedefs/time.h.html)
            #   defines optional CLOCK_MONOTONIC provided by #include <time.h>
            # Git's configure.ac:
            #   https://github.com/git/git/blob/v2.32.0/configure.ac#L1078
            has_monotonic_clock = CCompiler.does_source_compile(
                '#include <time.h>\n'
                'clockid_t id = CLOCK_MONOTONIC;')
            dlb.di.inform(f'detected monotonic clock: {has_monotonic_clock}')

            class GenerateConfigurationFile(dlb_contrib.clike.GenerateHeaderFile):
                PATH_COMPONENTS_TO_STRIP = len(output_directory.components)

                def write_content(self, file):
                    file.write(f'\n#define CONFIGURATION_HAS_MONOTONIC_CLOCK {"1" if has_monotonic_clock else "0"}\n')

            GenerateConfigurationFile(output_file=configuration_file).start()


def build():
    with dlb.di.Cluster('build'):
        with dlb.di.Cluster('compile'), dlb.ex.Context(max_parallel_redo_count=4):
            compile_results = [
                CCompiler(
                    source_files=[p],
                    object_files=[output_directory / p.with_appended_suffix('.o')],
                    include_search_directories=[source_directory, generated_source_directory]
                ).start()
                for p in source_directory.iterdir(name_filter=r'.+\.c', is_dir=False)
            ]

        with dlb.di.Cluster('link'), dlb.ex.Context():
            application_file = CLinker(
                object_and_archive_files=[r.object_files[0] for r in compile_results],
                linked_file=output_directory / 'application').start().linked_file

    return [application_file] + ['README.md']  # files to distribute


def collect_for_distribution(files):
    with dlb.di.Cluster('collect for distribution'):
        dlb_contrib.filesystem.FileCollector(
            input_files=files,
            output_directory=dist_directory
        ).start(force_redo=True)


# compile and link application written in C
with dlb.ex.Context():
    configure()
    collect_for_distribution(build())

dlb.di.inform('finished successfully')
