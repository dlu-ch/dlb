# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file.
#    python3 "$PWD"/build-all.py'   # in the directory of this file.

import dlb.fs
import dlb.ex
import dlb_contrib.msvc


def setup_paths_for_msvc(context):
    # see <program-dir>\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars*.bat
    context.env.import_from_outer('INCLUDE', restriction=r'[^;]+(;[^;]+)*', example='C:\\X;D:\\Y')
    context.env.import_from_outer('LIB', restriction=r'[^;]+(;[^;]+)*', example='C:\\X;D:\\Y')
    context.env.import_from_outer('VCTOOLSINSTALLDIR', restriction=r'.+',
                                  example='C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\'
                                          'VC\\Tools\\MSVC\\14.25.28610\\')
    context.env.import_from_outer('SYSTEMROOT', restriction=r'.+', example='C:\\WINDOWS')

    install_dir_path = dlb.fs.Path(dlb.fs.Path.Native(context.env['VCTOOLSINSTALLDIR']), is_dir=True)
    binary_path = install_dir_path / 'bin/Hostx64/x64/'
    context.helper['cl.exe'] = binary_path / 'cl.exe'
    context.helper['link.exe'] = binary_path / 'link.exe'


# compile and link application written in C
with dlb.ex.Context():
    setup_paths_for_msvc(dlb.ex.Context.active)

    source_path = dlb.fs.Path('src/')
    output_path = dlb.fs.Path('build/out/')

    compile_results = [
        dlb_contrib.msvc.CCompilerMsvc(
            source_files=[p],
            object_files=[output_path / p.with_appended_suffix('.o')],
            include_search_directories=[source_path]
        ).run()
        for p in source_path.list(name_filter=r'.+\.c') if not p.is_dir()
    ]

    object_files = [r.object_files[0] for r in compile_results]
    dlb_contrib.msvc.LinkerMsvc(
         linkable_files=object_files,
         linked_file=output_path / 'application.exe').run()
