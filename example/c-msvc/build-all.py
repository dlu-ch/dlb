# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file
#    python3 "$PWD"/build-all.py'   # in the directory of this file

import dlb.fs
import dlb.ex
import dlb_contrib.msvc
import dlb_contrib.msbatch


def setup_paths_for_msvc(context):
    # VCINSTALLDIR must be defined, the other environment variables are set by build/setup.bat with the help of
    # %VCINSTALLDIR%\VC\Auxiliary\Build\vcvars*.bat.
    context.env.import_from_outer('VCINSTALLDIR', pattern=r'.+\\',
                                  example='C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\')
    assert context.env['VCINSTALLDIR']
    environment = dlb_contrib.msbatch.RunEnvBatch(batch_file='build/setup.bat').start().exported_environment

    install_directory = dlb.fs.Path(dlb.fs.Path.Native(environment['VCTOOLSINSTALLDIR']), is_dir=True)
    binary_directory = install_directory / 'bin/Hostx64/x64/'
    context.helper['cl.exe'] = binary_directory / 'cl.exe'
    context.helper['link.exe'] = binary_directory / 'link.exe'

    context.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
    context.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*;?', example='C:\\X;D:\\Y')
    context.env.import_from_outer('LIB', pattern=r'[^;]+(;[^;]+)*;?', example='C:\\X;D:\\Y')
    context.env['INCLUDE'] = environment['INCLUDE']
    context.env['LIB'] = environment['LIB']


# compile and link application written in C
with dlb.ex.Context():
    setup_paths_for_msvc(dlb.ex.Context.active)

    source_directory = dlb.fs.Path('src/')
    output_directory = dlb.fs.Path('build/out/')

    compile_results = [
        dlb_contrib.msvc.CCompilerMsvc(
            source_files=[p],
            object_files=[output_directory / p.with_appended_suffix('.o')],
            include_search_directories=[source_directory]
        ).start()
        for p in source_directory.iterdir(name_filter=r'.+\.c', is_dir=False)
    ]

    object_files = [r.object_files[0] for r in compile_results]
    dlb_contrib.msvc.LinkerMsvc(
         linkable_files=object_files,
         linked_file=output_directory / 'application.exe').start()

dlb.di.inform('finished successfully')
