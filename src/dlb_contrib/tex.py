# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Typeset documents with TeX and LaTeX implementations based on web2c and kpathsea."""

# TeX: <https://www.tug.org/books/index.html#texbook>
# TeX: <https://ctan.org/tex-archive/systems/knuth/dist/tex/texbook.tex>
# LaTeX: <https://www.latex-project.org/>
# pdflatex: <https://www.tug.org/applications/pdftex/>
# LaTeX font encodings: <https://www.latex-project.org/help/documentation/encguide.pdf>
# Tested with: pdfTeX 3.14159265-2.6-1.40.19 (TeX Live 2019/dev/Debian) kpathsea version 6.3.1/dev
# Tested with: pdfTeX 3.14159265-2.6-1.40.21 (TeX Live 2020/Debian) kpathsea version 6.3.2
# Executable: 'tex'
# Executable: 'latex'
#
# Usage example:
#
#   import dlb.ex
#   import dlb_contrib.tex
#
#   with dlb.ex.Context():
#       output_directory = dlb.fs.Path('build/out/')
#
#       dlb_contrib.tex.Latex(
#           toplevel_file='src/report.tex', output_file=output_directory / 'report.dvi',
#           input_search_directories=['src/'],
#           state_files=[output_directory / 'report.aux',
#           output_directory / 'report.toc']
#       ).start()

__all__ = [
    'SPECIAL_CHARACTERS',
    'TexInputPath', 'KpathseaPath', 'KpathseaSearchPath', 'TexPath',
    'accessed_files_from_recorded',
    'Tex', 'Latex'
]

import sys
import os
import shutil
from typing import Iterable, List, Tuple, Union

import dlb.di
import dlb.fs
import dlb.ex

assert f'string' and sys.version_info >= (3, 7)


# 7 bit ASCII characters except ones that have a default category code assigned other than "space" (10), "letter" (11),
# or "other character" (12) according to TEXbook, p. 37.
# Namely:
#   - "escape character" (0)
#   - "beginning of group" (1)
#   - "end of group" (2)
#   - "math shift" (3)
#   - "alignment tab" (4)
#   - "end of line" (5)
#   - "parameter" (6)
#   - "superscript" (7)
#   - "subscript" (8)
#   - "ignored character" (9)
#   - "active character" (13)
#   - "comment character" (14)
#   - "invalid character" (15)
SPECIAL_CHARACTERS = frozenset('\\{}$&\r#^_\0~%\x7F')
assert len(SPECIAL_CHARACTERS) == 13


def _check_option(option: str) -> str:
    option = str(option)
    if option[:1] != '-':
        raise ValueError(f"not an option: {option!r}")  # would change meaning of following arguments
    return option


class TexInputPath(dlb.fs.Path):
    # Path that is - with prepended './' - suitable for inclusion into a (La)TeX file with '\input{...}',
    # assuming default category codes for all printable ASCII characters.
    #
    # Note: '^^;' acts exactly like '{'. E.g. '\input{a^^;b.tex}' leads to 'Runaway text? a{b.tex}'.

    RESERVED_CHARACTERS = frozenset(SPECIAL_CHARACTERS - {' ', '$'})

    def check_restriction_to_base(self, components_checked: bool):
        if not components_checked:
            for c in self.parts:
                invalid_characters = set(c) & TexInputPath.RESERVED_CHARACTERS
                if invalid_characters:
                    raise ValueError("must not contain reserved characters: {0}".format(
                        ','.join(repr(c) for c in sorted(invalid_characters))))

                if '  ' in c:
                    raise ValueError("must not contain multiple consecutive spaces")

                max_character = max(c)
                if ord(max_character) >= 0x80:
                    raise ValueError(f"must not contain only (7 bit) ASCII characters, not {max_character!r}")


class KpathseaPath(dlb.fs.RelativePath):
    # kpathsea:
    # see https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/kpathsea/path-elt.c?view=markup#l63
    #
    # - '$', ',', '{', '}' cannot be escaped in TEXINPUTS
    # - path must not start with '!!'
    # - '\n', '\r' in TEXINPUTS but not in the tools that use it
    # - #if defined(WIN32): '\\' is replaced by '/'
    #
    # web2c:
    # see https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/web2c/lib/texmfmp.c?view=markup#l847,
    # https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/web2c/lib/texmfmp.c?view=markup#l816
    #
    # - is treated differently if contains "'" or '"'

    UNSAFE_CHARACTERS = frozenset('${}\n\r\\"\'')

    def check_restriction_to_base(self, components_checked: bool):
        if not components_checked:
            for c in self.parts:
                invalid_characters = set(c) & KpathseaPath.UNSAFE_CHARACTERS
                if invalid_characters:
                    raise ValueError("must not contain reserved characters: {0}".format(
                        ','.join(repr(c) for c in sorted(invalid_characters))))


class KpathseaSearchPath(dlb.fs.RelativePath):
    # kpathsea: see
    # - https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/kpathsea/path-elt.c?view=markup#l63
    # - https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/kpathsea/c-pathch.h?view=markup#l77
    #
    # - ENV_SEP cannot be escaped in TEXINPUTS; ENV_SEP can be one of the following: ' ', ',', ';', ':'.

    UNSAFE_CHARACTERS = frozenset(' ,;:')

    def check_restriction_to_base(self, components_checked: bool):
        if not components_checked:
            for c in self.parts:
                invalid_characters = set(c) & KpathseaSearchPath.UNSAFE_CHARACTERS
                if invalid_characters:
                    raise ValueError("must not contain reserved characters: {0}".format(
                        ','.join(repr(c) for c in sorted(invalid_characters))))


class TexPath(TexInputPath, KpathseaPath):
    def check_restriction_to_base(self, components_checked: bool):
        # File name   TeX         os.path.splitext()
        # ---         ---         ---
        #
        # 'tex'       'tex.log'   ('tex', '')     # disallow (ambiguous)
        # 'tex.'      'tex.log'   ('tex', '.')
        # 'tex..'     'tex..log   ('tex.', '.')
        # '.tex'      '.log'      ('.tex', '')    # disallow (no basename)
        # '..tex'     '..log'     ('..tex', '')
        # '...'       '...log'    ('...', '')
        # '.tex.'     '.tex.log'  ('.tex', '.')
        # 'tex..tex'  'tex..log'  ('tex.', '.tex')

        if not self.is_dir():
            base_filename, ext = os.path.splitext(self.components[-1])
            if not ext:
                raise ValueError("must have a (non-empty) extension")


def accessed_files_from_recorded(context, recorder_output_file: dlb.fs.Path) \
        -> Tuple[List[dlb.fs.Path], List[dlb.fs.Path]]:

    # -recorder:
    #
    #     Create <base-file>.fls with texk/web2c/lib/openclose.c.
    #     https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/web2c/lib/openclose.c?view=markup#l76
    #     https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/web2c/lib/openclose.c?view=markup#l83
    #     Paths can contain arbitrary characters except '\n' and '\r'.
    #     This includes the absolute path of the working directory.

    read_files = []
    written_files = []

    working_tree_path_by_path = {}

    with open((context.root_path / recorder_output_file).native, 'rb') as f:
        pwd = None
        for line in f:
            path = None
            is_output = None
            line = line.rstrip(b'\r\n')
            if line.startswith(b'PWD '):
                pwd = line[4:].decode(sys.getfilesystemencoding())
                if not os.path.isabs(pwd):
                    raise ValueError(f"invalid line in {recorder_output_file.as_string()!r}: {line!r}")
            elif line.startswith(b'INPUT '):
                path = line[6:].decode(sys.getfilesystemencoding())
                is_output = False
            elif line.startswith(b'OUTPUT '):
                path = line[7:].decode(sys.getfilesystemencoding())
                is_output = True
            else:
                raise ValueError(f"invalid line in {recorder_output_file.as_string()!r}: {line!r}")
            if pwd and path and not os.path.isabs(path):
                path = os.path.join(pwd, path)
                if path in working_tree_path_by_path:
                    working_tree_path = working_tree_path_by_path[path]
                else:
                    try:
                        working_tree_path = context.working_tree_path_of(dlb.fs.Path.Native(path),
                                                                         existing=True, allow_temporary=True)
                        working_tree_path_by_path[path] = working_tree_path
                    except ValueError:
                        working_tree_path = None
                if working_tree_path is not None:
                    seq = written_files if is_output else read_files
                    if working_tree_path not in seq:
                        seq.append(working_tree_path)

    return read_files, written_files


class Tex(dlb.ex.Tool):
    # Dynamic helper, looked-up in the context.
    EXECUTABLE = 'tex'

    # Command line parameters for *EXECUTABLE* to output version information on standard output
    VERSION_PARAMETERS = ('-version',)

    # Filename extension of output file generated by *EXECUTABLE*.
    OUTPUT_EXTENSION = 'dvi'

    toplevel_file = dlb.ex.input.RegularFile(cls=TexPath)
    output_file = dlb.ex.output.RegularFile()

    # Copies of files generated by *EXECUTABLE* to keep between run.
    # The file extension must be the same as the file generated by *EXECUTABLE*.
    # The file extensions of all files in *state_files* must be different.
    # Example: ['build/out/report.aux'].
    # When the content of one of these changes, a redo is necessary.
    state_files = dlb.ex.output.RegularFile[:](replace_by_same_content=False)

    # Copy of log file generated by *EXECUTABLE* to keep after a run, even if unsuccessful.
    # The file extension must be the same as the file generated by *EXECUTABLE*.
    log_file = dlb.ex.output.RegularFile(required=False)

    included_files = dlb.ex.input.RegularFile[:](explicit=False)
    input_search_directories = dlb.ex.input.Directory[:](required=False, cls=KpathseaSearchPath)

    # Directory of .aux, .log etc. and working directory for *EXECUTABLE*.
    # If not set, a temporary directory is used.
    intermediary_directory = dlb.ex.output.Directory(required=False)

    # Global search paths in environment variable TEXINPUTS are *appended* (unchanged) to the ones
    # in *input_search_directories*.
    # Must not contain unexpanded variables (because these are not imported).
    global_input_search_paths = dlb.ex.input.EnvVar(name='TEXINPUTS', pattern=r'[^$]*', example='.:~/tex//:',
                                                    required=False, explicit=False)
    # Environment variables:
    # https://www.tug.org/texinfohtml/kpathsea.html
    # https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/kpathsea/texmf.in?view=markup

    def get_options(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
        return []

    async def redo(self, result, context):
        with context.temporary(is_dir=True) as intermediary_directory:
            if self.intermediary_directory is not None:
                intermediary_directory = self.intermediary_directory
            intermediary_directory = context.working_tree_path_of(intermediary_directory,
                                                                  existing=True, allow_temporary=True)
            if self.intermediary_directory is not None:
                (context.root_path / intermediary_directory).native.raw.mkdir(parents=True, exist_ok=True)

            # note: --cnf-line=texmf_casefold_search=0 is not supported with
            # pdfTeX 3.14159265-2.6-1.40.19 (TeX Live 2019/dev/Debian) kpathsea version 6.3.1/dev
            arguments = [
                '-interaction=nonstopmode', '-halt-on-error', '-file-line-error', '-no-shell-escape',
                '-recorder'  # create .fls file
            ]
            arguments += [_check_option(c) for c in self.get_options()]
            arguments += [self.toplevel_file]  # must be last

            # Note: since this tool is only called if *self.toplevel_file* exists, a potential fallback to a similar
            # file name (e.g. with added suffix or "case folding") does not matter for *self.toplevel_file*.
            # It does, however, for files included - directly or indirectly - *self.toplevel_file*.

            # compile TEXINPUTS
            texinputs = []
            if self.input_search_directories:
                texinputs = [
                    str(context.working_tree_path_of(p, existing=True, allow_temporary=True).relative_to(
                        intermediary_directory, collapsable=True).native)
                    for p in self.input_search_directories
                ]
            texinputs += [result.global_input_search_paths.raw] if result.global_input_search_paths else ['']
            # https://www.tug.org/svn/pdftex/tags/pdftex-1.40.19/source/src/texk/kpathsea/c-pathch.h?view=markup#l77
            env = {'TEXINPUTS': os.pathsep.join(texinputs)}

            base_filename, _ = os.path.splitext(self.toplevel_file.components[-1])
            recorder_output_file = intermediary_directory / f'{base_filename}.fls'

            # copy state files to temporary (working) directory
            restored_state_files = []
            state_file_by_suffix = {}
            for state_file in self.state_files:
                _, suffix = os.path.splitext(state_file.components[-1])
                state_file_with_same_suffix = state_file_by_suffix.get(suffix)
                if state_file_with_same_suffix is not None:
                    raise ValueError(
                        f"'state_file' contains more than one path with suffix {suffix!r}: "
                        f"{state_file_with_same_suffix.as_string()!r}, {state_file.as_string()!r}"
                    )
                state_file_by_suffix[suffix] = state_file
                restored_state_file = intermediary_directory / f'{base_filename}{suffix}'
                restored_state_files.append(restored_state_file)
                abs_state_file = context.root_path / state_file
                if os.path.isfile(abs_state_file.native):
                    shutil.copy(src=abs_state_file.native, dst=(context.root_path / restored_state_file).native)

            # remove log file
            if self.log_file and os.path.isfile(self.log_file.native):
                os.unlink(self.log_file.native)

            cwd = str((context.root_path / intermediary_directory).native)
            for c in '\n\r':
                if c in cwd:
                    raise RuntimeError(f'current working directory must not contain {c!r}')  # for -recorder

            try:
                await context.execute_helper(self.EXECUTABLE, arguments, cwd=intermediary_directory, forced_env=env)
            finally:
                if self.log_file:
                    _, suffix = os.path.splitext(self.log_file.components[-1])
                    new_log_file = intermediary_directory / f'{base_filename}{suffix}'
                    if os.path.isfile(new_log_file.native):
                        context.replace_output(result.log_file, new_log_file)

            read_files, written_files = accessed_files_from_recorded(context, recorder_output_file)

            needs_redo = False
            for state_file in self.state_files:
                _, suffix = os.path.splitext(state_file.components[-1])
                new_state_file = intermediary_directory / f'{base_filename}{suffix}'
                if not os.path.isfile(state_file.native):
                    needs_redo = True
                needs_redo = context.replace_output(state_file, new_state_file) or needs_redo

            try:
                read_files.remove(result.toplevel_file)
            except ValueError:
                pass
            if self.state_files:
                read_files = [p for p in read_files if p not in restored_state_files]

            read_files_in_managed_tree = []
            for p in read_files:
                try:
                    read_files_in_managed_tree.append(context.working_tree_path_of(p, existing=True))
                except ValueError:
                    pass

            result.included_files = sorted(read_files_in_managed_tree)
            output_file = intermediary_directory / f'{base_filename}.{self.OUTPUT_EXTENSION}'
            if not os.path.exists(str(output_file.native)):
                raise ValueError(f'output file missing (no pages): {output_file.as_string()!r}')

            context.replace_output(result.output_file, context.root_path / output_file)

            read_and_written_files = sorted(set(read_files) & set(written_files))
            if read_and_written_files:
                dlb.di.inform(
                    f"{len(read_and_written_files)} file(s) were read and written "
                    f"(consider adding them to 'state_files'):",
                    *[f'{p.as_string()!r}' for p in read_and_written_files],
                    level=dlb.di.WARNING
                )

        return needs_redo


class Latex(Tex):
    EXECUTABLE = 'latex'
