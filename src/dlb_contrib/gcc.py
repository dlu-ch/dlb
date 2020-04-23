# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Compile and link languages of the C family with the GNU Compiler Collection (with the help of the
linker from the GNU Binutils)."""

# GCC: <https://gcc.gnu.org/>
# GNU Binutils: <https://www.gnu.org/software/binutils/>
# Tested with: gcc 8.3.0
# Executable: 'gcc'
# Executable: 'g++'
#
# Usage example:
#
#     import dlb.ex
#     import dlb_contrib.gcc
#
#     with dlb.ex.Context():
#         source_path = dlb.fs.Path('src/')
#         output_path = dlb.fs.Path('build/out/')
#
#         compile_results = [
#             dlb_contrib.gcc.CCompilerGcc(
#                 source_files=[p],
#                 object_files=[output_path / p.with_appended_suffix('.o')],
#                 include_search_directories=[source_path]
#             ).run()
#             for p in source_path.iterdir(name_filter=r'.+\.c', is_dir=False)
#         ]
#
#         dlb_contrib.gcc.CLinkerGcc(
#             object_and_archive_files=[r.object_files[0] for r in compile_results],
#             linked_file=output_path / 'application').run()

__all__ = [
    'Path', 'ObjectOrArchivePath',
    'CCompilerGcc', 'CplusplusCompilerGcc',
    'CLinkerGcc', 'CplusplusLinkerGcc'
]


import sys
import os.path
from typing import Iterable, Union

import dlb.fs
import dlb.ex
import dlb_contrib.gnumake
import dlb_contrib.clike

assert sys.version_info >= (3, 7)


class Path(dlb.fs.PosixPath):
    UNSAFE_CHARACTERS = ':;\n\r'  # disallow ';' because of Makefile rules

    def check_restriction_to_base(self, components_checked: bool):
        if components_checked:
            return
        if any(s in c for c in self.parts for s in self.UNSAFE_CHARACTERS):
            raise ValueError("must not contain these characters: {0}".format(
                ','.join(repr(c) for c in sorted(self.UNSAFE_CHARACTERS))))


class ObjectOrArchivePath(Path):
    def check_restriction_to_base(self, components_checked: bool):
        if not self.is_dir() and self.parts:
            _, ext = os.path.splitext(self.parts[-1])
            if ext not in ('.o', '.a'):
                raise ValueError("must end with '.o' or '.a'")


def _check_warning_name(name: str) -> str:
    name = str(name)
    if not name or name.startswith('no-') or '=' in name:
        raise ValueError(f"not a warning name: {name!r}")  # not usable after -W or -Werror=
    return name


class _CompilerGcc(dlb_contrib.clike.ClikeCompiler):
    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'gcc'

    # Names of warnings to be suppressed (e.g. 'unused-value').
    SUPPRESSED_WARNINGS = ()

    # Names of warnings that should make the compilation unsuccessful.
    FATAL_WARNINGS = ('all',)

    source_files = dlb.ex.input.RegularFile[1:](cls=Path)
    include_search_directories = dlb.ex.input.Directory[:](required=False, cls=Path)

    async def redo(self, result, context):
        if len(result.object_files) != len(result.source_files):
            raise ValueError("'object_files' must be of same length as 'source_files'")

        compile_arguments = [c for c in self.get_compile_arguments()]

        # https://gcc.gnu.org/onlinedocs/gcc/Directory-Options.html#Directory-Options
        if self.include_search_directories:
            for p in self.include_search_directories:
                # note: '=' or '$SYSROOT' would be expanded by GCC
                # str(p.native) never starts with these
                compile_arguments.extend(['-I', p])  # looked up for #include <p> and #include "p"

        # https://gcc.gnu.org/onlinedocs/gcc/Warning-Options.html
        compile_arguments += ['-Wall']
        compile_arguments += ['-Wno-' + _check_warning_name(n) for n in self.SUPPRESSED_WARNINGS]
        compile_arguments += ['-Werror=' + _check_warning_name(n) for n in self.FATAL_WARNINGS]

        for macro, replacement in self.DEFINITIONS.items():
            if not dlb_contrib.clike.SIMPLE_IDENTIFIER.match(macro) and \
                    not dlb_contrib.clike.FUNCTIONLIKE_MACRO.match(macro):
                raise ValueError(f"not a macro: {macro!r}")
            # *macro* is a string that does not start with '-' and does not contain '='
            if replacement is None:
                compile_arguments += ['-U', macro]
            else:
                replacement = str(replacement).strip()
                if replacement == '1':
                    compile_arguments += ['-D', macro]
                else:
                    compile_arguments += ['-D', f'{macro}={replacement}']

        included_files = set()

        # compile
        for source_file, object_file in zip(result.source_files, result.object_files):
            with context.temporary() as make_rules_file, context.temporary() as temp_object_file:
                await context.execute_helper(
                    self.EXECUTABLE,
                    compile_arguments + [
                        '-x', self.LANGUAGE, '-std=' + self.DIALECT, '-c', '-o', temp_object_file,
                        '-MMD', '-MT', '_ ', '-MF', make_rules_file,
                        source_file
                    ]
                )

                # parse content of make_rules_file as a Makefile and add all paths in managed tree to included_files
                with open(make_rules_file.native, 'r', encoding=sys.getfilesystemencoding()) as dep_file:
                    for p in dlb_contrib.gnumake.additional_sources_from_rule(dep_file):
                        try:
                            included_files.add(context.working_tree_path_of(p))
                        except ValueError:
                            pass

                context.replace_output(object_file, temp_object_file)

        result.included_files = sorted(included_files)


class CCompilerGcc(_CompilerGcc):
    LANGUAGE = 'c'
    DIALECT = 'c99'  # https://gcc.gnu.org/onlinedocs/gcc/C-Dialect-Options.html#C-Dialect-Options


class CplusplusCompilerGcc(_CompilerGcc):
    LANGUAGE = 'c++'
    DIALECT = 'c++11'  # https://gcc.gnu.org/onlinedocs/gcc/C-Dialect-Options.html#C-Dialect-Options


class _LinkerGcc(dlb.ex.Tool):
    # Link with with gcc, gcc subprograms and the GNU linker.

    # Dynamic helper, looked-up in the context.
    EXECUTABLE = ''  # define in subclass

    # Tuple of library name to be searched in the library search directories and linked against.
    # Order matters; if library *b* depends on *a*, *b* should precede *a* in the sequence
    LIBRARY_FILENAMES = ()  # e.g. 'libxy.a'

    # Object files and static libraries to link.
    # Order matters; if file *b* depends on *a*, *b* should precede *a* in the sequence.
    object_and_archive_files = dlb.ex.input.RegularFile[1:](cls=ObjectOrArchivePath)

    linked_file = dlb.ex.output.RegularFile(replace_by_same_content=False)

    # Tuple of paths of directories that are to be searched for libraries in addition to the standard system directories
    library_search_directories = dlb.ex.input.Directory[:](required=False, cls=Path)

    # Subprograms like 'ld', 'collect2' are searched in this directory.
    # If not set, the directory of EXECUTABLE is used. See GCC_EXEC_PREFIX in gcc documentation for details.
    subprogram_directory = dlb.ex.input.Directory(required=False, cls=Path)

    def get_link_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return []  # e.g. '-shared'

    # gcc -dumpspecs

    async def redo(self, result, context):
        link_arguments = [c for c in self.get_link_arguments()]

        if self.library_search_directories:
            for p in self.library_search_directories:
                link_arguments.extend(['-L', p])  # looked up for -lxxx

        # https://gcc.gnu.org/onlinedocs/gcc/Directory-Options.html#Directory-Options
        # absolute path prevents the mentioned "special cludge"
        if result.subprogram_directory is None:
            abs_subprogram_directory = context.helper[self.EXECUTABLE][:-1]
        else:
            abs_subprogram_directory = result.subprogram_directory
            if not abs_subprogram_directory.is_absolute():
                abs_subprogram_directory = context.root_path / abs_subprogram_directory

        # link
        with context.temporary() as linked_file:
            link_arguments += [
                '-B' + abs_subprogram_directory.as_string(),
                '-o', linked_file,
                *result.object_and_archive_files  # note: type detection by suffix of path cannot be disabled
            ]

            # https://linux.die.net/man/1/ld
            for lib in self.LIBRARY_FILENAMES:
                link_arguments += ['-l:' + lib]  # if l is empty: '/usr/bin/ld: cannot find -l:'

            await context.execute_helper(self.EXECUTABLE, link_arguments)
            context.replace_output(result.linked_file, linked_file)


class CLinkerGcc(_LinkerGcc):
    EXECUTABLE = 'gcc'


class CplusplusLinkerGcc(_LinkerGcc):
    EXECUTABLE = 'g++'
