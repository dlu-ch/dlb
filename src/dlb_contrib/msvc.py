# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Compile and link the Microsoft dialects of C and C++ with Microsoft Visual Studio platform toolset."""

# Microsoft Visual Studio Community: <https://visualstudio.microsoft.com/de/thank-you-downloading-visual-studio/?sku=Community>
# Visual Studio platform toolset: <https://docs.microsoft.com/en-us/cpp/build/building-on-the-command-line?view=vs-2019>
# cl: <https://docs.microsoft.com/en-us/cpp/build/reference/compiling-a-c-cpp-program?view=vs-2019>
# link: <https://docs.microsoft.com/en-us/cpp/build/reference/linking?view=vs-2019>
# Tested with: MSVC v142 (part of Microsoft Visual Studio Community 2019)
# Executable: 'cl.exe'
# Executable: 'link.exe'
#
# Usage example:
#
#   import dlb.fs
#   import dlb.ex
#   import dlb_contrib.msvc
#
#   def setup_paths_for_msvc(context):
#       # VCINSTALLDIR must be defined, the other environment variables are set by build/setup.bat with the help of
#       # %VCINSTALLDIR%\VC\Auxiliary\Build\vcvars*.bat.
#       context.env.import_from_outer('VCINSTALLDIR', pattern=r'.+\\',
#                                     example='C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\')
#       environment = dlb_contrib.msbatch.RunEnvBatch(batch_file='build/setup.bat').start().environment
#
#       install_directory = dlb.fs.Path(dlb.fs.Path.Native(environment['VCTOOLSINSTALLDIR']), is_dir=True)
#       binary_directory = install_directory / 'bin/Hostx64/x64/'
#       context.helper['cl.exe'] = binary_directory / 'cl.exe'
#       context.helper['link.exe'] = binary_directory / 'link.exe'
#
#       context.env.import_from_outer('SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS')
#       context.env.import_from_outer('INCLUDE', pattern=r'[^;]+(;[^;]+)*;?', example='C:\\X;D:\\Y')
#       context.env.import_from_outer('LIB', pattern=r'[^;]+(;[^;]+)*;?', example='C:\\X;D:\\Y')
#       context.env['INCLUDE'] = environment['INCLUDE']
#       context.env['LIB'] = environment['LIB']
#
#   with dlb.ex.Context():
#       setup_paths_for_msvc(dlb.ex.Context.active)
#
#       source_directory = dlb.fs.Path('src/')
#       output_directory = dlb.fs.Path('build/out/')
#
#       compile_results = [
#           dlb_contrib.msvc.CCompilerMsvc(
#               source_files=[p],
#               object_files=[output_directory / p.with_appended_suffix('.o')],
#               include_search_directories=[source_directory]
#           ).start()
#           for p in source_directory.iterdir(name_filter=r'.+\.c', is_dir=False)
#       ]
#
#       object_files = [r.object_files[0] for r in compile_results]
#       dlb_contrib.msvc.LinkerMsvc(
#            linkable_files=object_files,
#            linked_file=output_directory / 'application.exe'
#       ).start()

__all__ = ['CCompilerMsvc', 'CplusplusCompilerMsvc', 'LinkerMsvc']

import sys
import os.path
import re
from typing import List, Set, Tuple, Union

import dlb.fs
import dlb.ex
import dlb_contrib.clike
import dlb_contrib.mscrt

assert sys.version_info >= (3, 7)


INCLUDE_LINE_REGEX = re.compile(rb'^[^ \t][^:]*: [^ \t][^:]*: +')
assert INCLUDE_LINE_REGEX.match(b'Note: including file: D:\\dir\\included_file.h')


async def _detect_include_line_representation(context, compiler_executable) -> Tuple[bytes, bytes, str]:
    try:
        # https://docs.microsoft.com/en-us/windows/console/getconsoleoutputcp
        import ctypes
        codepage: int = ctypes.windll.kernel32.GetConsoleOutputCP()
        assert codepage > 0
    except Exception:
        raise RuntimeError('failed to get ANSI codepage of process') from None

    encoding = f'cp{codepage:03}'  # _not_ the one returned by locale.getpreferredencoding()
    try:
        import codecs
        codecs.lookup(encoding)
    except LookupError:
        raise RuntimeError(f'ANSI codepage of process not supported: {encoding!r}') from None

    # MS Windows/MSVC do not provide a way to set the message language (UI culture) without changing global
    # settings that would affect other processes as well.
    # Therefore: Query the message for the current message language.
    with context.temporary(is_dir=True) as temp_dir:
        probe_file = temp_dir / 'include_probe_file.h'
        open(probe_file.native, 'xb').close()
        temp_source_file = temp_dir / 'm.c'
        with open(temp_source_file.native, 'xb') as f:
            f.write(b'#include "include_probe_file.h"\n')
        _, output = await context.execute_helper_with_output(
            compiler_executable, ['/nologo', '/showIncludes', '/c', temp_source_file],
            cwd=temp_dir, other_output=False
        )
        native_path_suffix = str(context.working_tree_path_of(probe_file, existing=True, collapsable=True,
                                                              allow_temporary=True).native)
    assert native_path_suffix[0] == '.'
    native_path_suffix = native_path_suffix[1:].encode('ascii')

    include_line_prefix = None
    working_tree_native_path_prefix = None

    for line in output.splitlines():
        if line.endswith(native_path_suffix):
            m = INCLUDE_LINE_REGEX.match(line)
            if not m:
                raise RuntimeError(f"unexpected include line for '/showIncludes': {line!r}")
            include_line_prefix = m.group()
            working_tree_native_path_prefix = line[len(include_line_prefix):][:-len(native_path_suffix) + 1]
            if not len(working_tree_native_path_prefix) > 2:  # C:\
                raise RuntimeError(f"cannot get working tree's root from this: {line!r}")
            break
    if not include_line_prefix:
        raise RuntimeError("failed to detect include line for '/showIncludes'")

    return include_line_prefix, working_tree_native_path_prefix, encoding


class IncludeLineProcessor(dlb.ex.ChunkProcessor):
    separator = b'\r\n'
    max_chunk_size = 16 * 1024  # maximum chunk size (without separator)

    def __init__(self, include_line_prefix: bytes, working_tree_native_path_prefix: bytes, encoding: str):
        self.include_line_prefix = include_line_prefix
        self.working_tree_native_path_prefix = working_tree_native_path_prefix
        self.encoding = encoding
        self.result = set()

    def process(self, chunk: bytes, is_last: bool):
        # Note about the output due to /showIncludes:
        # - The file paths start with a directory path as given in INCLUDES or with /D (relative or absolute).
        # - When a characters in the path is not part of the process's ANSI codepage it is replaced by a
        #   similar character.
        # - Hence the file path representation of the MSVC compiler is ambiguous - there is no way of accessing the
        #   missing information.

        is_include_line = chunk.startswith(self.include_line_prefix)
        if is_include_line:
            # https://docs.microsoft.com/en-us/cpp/build/reference/unicode-support-in-the-compiler-and-linker?view=vs-2019:
            # During compilation, the compiler outputs diagnostics to the console in UTF-16.
            # The characters that can be displayed at your console depend on the console window properties.
            # Compiler output redirected to a file is in the current ANSI console codepage.
            path = chunk[len(self.include_line_prefix):].lstrip()
            if path.startswith(self.working_tree_native_path_prefix):
                # each path for a file in the working tree starts with *working_tree_native_path_prefix*
                # (but - due to ambiguity in ANSI path representation - a file outside the working tree can
                # also start with *working_tree_native_path_prefix*)
                path = path[len(self.working_tree_native_path_prefix):].lstrip(b'\\/')
            elif os.path.isabs(path):
                path = None
            if path:
                self.result.add(path.decode(self.encoding))
        elif chunk:
            sys.stdout.write(chunk.decode(self.encoding) + '\r\n')


class _CompilerMsvc(dlb_contrib.clike.ClikeCompiler):
    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'cl.exe'

    system_root_directory_path = dlb.ex.input.EnvVar(
        name='SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS',
        required=True, explicit=False)
    system_include_search_directories = dlb.ex.input.EnvVar(
        name='INCLUDE', pattern=r'[^;]+(;[^;]+)*;?', example='C:\\X;D:\\Y',
        required=True, explicit=False)

    def get_include_compile_arguments(self) -> List[Union[str, dlb.fs.Path]]:
        compile_arguments = []
        if self.include_search_directories:
            for p in self.include_search_directories:
                compile_arguments.extend(['/I', p])
        return compile_arguments

    def get_definition_compile_arguments(self) -> List[Union[str, dlb.fs.Path]]:
        compile_arguments = []
        # https://docs.microsoft.com/en-us/cpp/build/reference/d-preprocessor-definitions?view=vs-2019:
        # The /D option doesn't support function-like macro definitions.
        for macro, replacement in self.DEFINITIONS.items():
            if not dlb_contrib.clike.SIMPLE_IDENTIFIER_REGEX.match(macro):
                raise ValueError(f"not an object-like macro: {macro!r}")
            # *macro* is a string that does not start with '/' and does not contain '=' or '#'
            if replacement is None:
                # https://docs.microsoft.com/en-us/cpp/build/reference/u-u-undefine-symbols?view=vs-2019:
                # Neither the /U or /u option can undefine a symbol created by using the #define directive.
                # The /U option can undefine a symbol that was previously defined by using the /D option.
                compile_arguments += ['/U', macro]
            else:
                replacement = str(replacement).strip()
                if replacement == '1':
                    compile_arguments += ['/D', macro]
                else:
                    compile_arguments += ['/D', f'{macro}={replacement}']
        return compile_arguments

    def get_all_compile_arguments(self) -> List[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        # Return list of all commandline arguments for *EXECUTABLE* that do not depend on source files
        compile_arguments = self.get_extra_compile_arguments()
        compile_arguments += self.get_include_compile_arguments()
        compile_arguments += self.get_definition_compile_arguments()
        return compile_arguments

    def get_included_files_from_paths(self, context, included_file_native_paths: Set[str], encoding) \
            -> List[dlb.fs.Path]:
        included_file_paths = []
        for p in included_file_native_paths:
            p = dlb.fs.Path(dlb.fs.Path.Native(p))
            try:
                included_file_paths.append(context.working_tree_path_of(p))
            except dlb.ex.WorkingTreePathError as e:
                if isinstance(e.oserror, OSError):
                    msg = (
                        f"reportedly included file not found: {p.as_string()!r}\n"
                        f"  | ambiguity in the ANSI encoding ({encoding!r}) of its path?"
                    )
                    raise FileNotFoundError(msg)
        included_file_paths.sort()
        return included_file_paths

    async def redo(self, result, context):
        if len(result.object_files) > len(result.source_files):
            raise ValueError("'object_files' must be of at most the same length as 'source_files'")
        optional_object_files = result.object_files + (None,) * (len(result.source_files) - len(result.object_files))

        compile_arguments = self.get_all_compile_arguments()

        include_line_prefix, working_tree_native_path_prefix, encoding = \
            await _detect_include_line_representation(context, self.EXECUTABLE)
        # each line emitted due to '/showIncludes' starts with *include_line_prefix*

        if self.LANGUAGE == 'c':
            language_option = '/Tc'
        elif self.LANGUAGE == 'c++':
            language_option = '/Tp'
        else:
            raise ValueError(f"invalid 'LANGUAGE': {self.LANGUAGE!r}")

        # compile
        included_file_native_paths: Set[str] = set()
        with context.temporary(is_dir=True) as temp_dir:
            for source_file, optional_object_file in zip(result.source_files, optional_object_files):
                processor = IncludeLineProcessor(include_line_prefix, working_tree_native_path_prefix, encoding)
                with context.temporary(suffix='.o') as temp_object_file:
                    _, included_file_paths = await context.execute_helper_with_output(
                        self.EXECUTABLE,
                        compile_arguments + [
                            '/nologo', '/showIncludes', '/c',

                            # must have a suffix, otherwise '.obj' is appended:
                            '/Fo' + str(temp_object_file.native),

                            language_option, source_file  # source_file must be preceded immediately by language_option
                        ], forced_env={'TMP': str(temp_dir.native)},
                        chunk_processor=processor
                    )
                    included_file_native_paths |= included_file_paths
                    if optional_object_file is not None:
                        context.replace_output(optional_object_file, temp_object_file)

        result.included_files = self.get_included_files_from_paths(context, included_file_native_paths, encoding)


class CCompilerMsvc(_CompilerMsvc):
    LANGUAGE = 'c'


class CplusplusCompilerMsvc(_CompilerMsvc):
    LANGUAGE = 'c++'


class LinkerMsvc(dlb.ex.Tool):
    # Link with with MSVC.

    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'link.exe'

    system_root_directory_path = dlb.ex.input.EnvVar(
        name='SYSTEMROOT', pattern=r'.+', example='C:\\WINDOWS',
        required=True, explicit=False)
    system_library_search_directories = dlb.ex.input.EnvVar(
        name='LIB', pattern=r'[^;]+(;[^;]+)*;?', example='C:\\X;D:\\Y',
        required=True, explicit=False)

    # Object files and static libraries to link.
    linkable_files = dlb.ex.input.RegularFile[1:]()

    linked_file = dlb.ex.output.RegularFile(replace_by_same_content=False)

    # Tuple of paths of directories that are to be searched for libraries in addition to the standard system directories
    library_search_directories = dlb.ex.input.Directory[:](required=False)

    def get_extra_link_arguments(self) -> List[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return []  # e.g. '/DLL'

    async def redo(self, result, context):
        link_arguments = ['/NOLOGO'] + self.get_extra_link_arguments()

        if self.library_search_directories:
            for p in self.library_search_directories:
                # https://docs.microsoft.com/en-us/cpp/build/reference/libpath-additional-libpath?view=vs-2019
                link_arguments.extend(['/LIBPATH:' + str(p.native)])

        # link
        with context.temporary() as response_file, context.temporary() as linked_file, \
                context.temporary(is_dir=True) as temp_dir:

            # https://docs.microsoft.com/en-us/cpp/build/reference/out-output-file-name?view=vs-2019
            link_arguments += [
                '/OUT:' + str(linked_file.native),

                *result.linkable_files
                # https://docs.microsoft.com/en-us/cpp/build/reference/link-input-files?view=vs-2019:
                # LINK does not use file extensions to make assumptions about the contents of a file.
                # Instead, LINK examines each input file to determine what kind of file it is.
            ]

            for a in link_arguments:
                if a[:1] == '@':
                    raise ValueError(f"argument must not start with '@': {a!r}")
            with open(response_file.native, 'w', encoding='utf-16') as f:
                link_arguments, _ = context.prepare_arguments(link_arguments)
                f.write(dlb_contrib.mscrt.list2cmdline(link_arguments))

            await context.execute_helper(self.EXECUTABLE, ['@' + str(response_file.native)],
                                         forced_env={'TMP': str(temp_dir.native)})
            context.replace_output(result.linked_file, linked_file)
