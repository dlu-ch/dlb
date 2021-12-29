# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.tex
import string
import sys
import os.path
import io
import unittest
from typing import Iterable, Union


class KpathseaPathTest(unittest.TestCase):
    def test_fails_for_absolute(self):
        with self.assertRaises(ValueError):
            dlb_contrib.tex.KpathseaPath('/a/b')

    def test_fails_for_backslash(self):
        with self.assertRaises(ValueError):
            dlb_contrib.tex.KpathseaPath('a\\b')

    def test_suceeds_for_separators(self):
        for c in ' ,;:':
            dlb_contrib.tex.KpathseaPath(f'a{c}b')

    def test_fails_for_variable(self):
        for c in '${}':
            with self.assertRaises(ValueError):
                dlb_contrib.tex.KpathseaPath(f'a{c}b')


class KpathseaSearchPathTest(unittest.TestCase):
    def test_fails_for_separators(self):
        for c in ' ,;:':
            with self.assertRaises(ValueError):
                dlb_contrib.tex.KpathseaSearchPath(f'a{c}b')


class TexInputPathTest(unittest.TestCase):

    def test_fails_for_most_special_characters(self):
        self.assertEqual(16 - 3, len(dlb_contrib.tex.SPECIAL_CHARACTERS))
        for c in dlb_contrib.tex.SPECIAL_CHARACTERS - {' ', '$'}:
            with self.subTest(character=c):
                with self.assertRaises(ValueError):
                    dlb_contrib.tex.TexInputPath(f'a{c}b')

        # '&' and '_':
        # - fails for TeX 3.14159265 (TeX Live 2019/dev/Debian) kpathsea version 6.3.1/dev
        # - succeeds for TeX 3.14159265 (TeX Live 2020/Debian) kpathsea version 6.3.2

        dlb_contrib.tex.TexInputPath(' ')
        dlb_contrib.tex.TexInputPath('$')

    def test_fails_with_multiple_consecutive_spaces(self):
        dlb_contrib.tex.TexInputPath('a b')
        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexInputPath('a  b')

    def test_fails_for_non_7bit_ascii(self):
        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexInputPath('a\x7Fb')
        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexInputPath('ätsch!')


class TexPathTest(unittest.TestCase):

    def test_fails_for_lineseparator(self):
        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexPath('a\nb.tex')

        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexPath('a\rb.tex')

    def test_suceeds_for_single_space(self):
        dlb_contrib.tex.TexPath('a b c.tex')

    def test_fails_with_multiple_consecutive_spaces(self):
        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexPath('a  b.tex')

    def test_fails_without_suffix_if_not_directory(self):
        dlb_contrib.tex.TexPath('tex', is_dir=True)

        for filename in ['tex', '.tex', '...']:
            with self.assertRaises(ValueError):
                dlb_contrib.tex.TexPath(filename)


class RecordedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_scenario1(self):
        with dlb.ex.Context() as context:
            os.mkdir('src')
            open(os.path.join('src', 'report.tex'), 'xb').close()  # must exist
            os.mkdir('out')
            recorded_file = dlb.fs.Path('out/recorded.fls')
            with open(recorded_file.native, 'xb') as f:
                f.write(
                    b'PWD ' + os.path.abspath('out').encode() + b'\n'
                    b'INPUT /etc/texmf/web2c/texmf.cnf\n'
                    b'INPUT /usr/share/texmf/web2c/texmf.cnf\n'
                    b'INPUT /usr/share/texlive/texmf-dist/web2c/texmf.cnf\n'
                    b'INPUT /var/lib/texmf/web2c/pdftex/pdflatex.fmt\n'
                    b'INPUT ../src/report.tex\n'
                    b'OUTPUT report.log\n'
                    b'INPUT /usr/share/texlive/texmf-dist/tex/latex/base/article.cls\n'
                    b'INPUT /usr/share/texlive/texmf-dist/tex/latex/base/article.cls\n'
                    b'INPUT /usr/share/texlive/texmf-dist/tex/latex/base/size10.clo\n'
                    b'INPUT /usr/share/texlive/texmf-dist/tex/latex/base/size10.clo\n'
                    b'INPUT report.aux\n'
                )
            read_files, written_files = \
                dlb_contrib.tex.accessed_files_from_recorded(context, recorded_file)

        self.assertEqual([dlb.fs.Path('src/report.tex'), dlb.fs.Path('out/report.aux')], read_files)
        self.assertEqual([dlb.fs.Path('out/report.log')], written_files)

    def test_empty_is_ok(self):
        open('recorded.fls', 'xb').close()
        with dlb.ex.Context() as context:
            read_files, written_files = \
                dlb_contrib.tex.accessed_files_from_recorded(context, dlb.fs.Path('recorded.fls'))
        self.assertEqual([], read_files)
        self.assertEqual([], written_files)

    def test_ignores_path_outside_working_tree(self):
        with dlb.ex.Context() as context:
            with open('recorded.fls', 'xb') as f:
                f.write(
                    b'PWD ' + os.getcwd().encode() + b'\n'
                    b'INPUT /var/lib/texmf/web2c/pdftex/pdflatex.fmt\n'
                    b'INPUT ../../../src/report.tex\n'
                    b'OUTPUT report.log\n'
                    b'INPUT ../../../src/report.tex\n'
                    b'INPUT report.aux\n'
                )
            read_files, written_files = \
                dlb_contrib.tex.accessed_files_from_recorded(context, dlb.fs.Path('recorded.fls'))

        self.assertEqual([dlb.fs.Path('report.aux')], read_files)
        self.assertEqual([dlb.fs.Path('report.log')], written_files)

    def test_fails_for_invalid_line(self):
        with dlb.ex.Context() as context:
            with open('recorded.fls', 'xb') as f:
                f.write(
                    b'PWD ' + os.getcwd().encode() + b'\n'
                    b'GUGUSELI dada\n'
                    b'INPUT /var/lib/texmf/web2c/pdftex/pdflatex.fmt\n'
                )
            with self.assertRaises(ValueError) as cm:
                dlb_contrib.tex.accessed_files_from_recorded(context, dlb.fs.Path('recorded.fls'))
            self.assertEqual("invalid line in 'recorded.fls': b'GUGUSELI dada'", str(cm.exception))

    def test_fails_for_relative_cwd(self):
        with dlb.ex.Context() as context:
            with open('recorded.fls', 'xb') as f:
                f.write(
                    b'PWD he/he\n'
                    b'INPUT /var/lib/texmf/web2c/pdftex/pdflatex.fmt\n'
                )
            with self.assertRaises(ValueError) as cm:
                dlb_contrib.tex.accessed_files_from_recorded(context, dlb.fs.Path('recorded.fls'))
            self.assertEqual("invalid line in 'recorded.fls': b'PWD he/he'", str(cm.exception))


@unittest.skipUnless(testenv.has_executable_in_path('tex'), 'requires latex in $PATH')
class TexTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_scenario1(self):
        os.mkdir('src')
        with open('report.tex', 'x', encoding='utf-8') as f:
            f.write('Hello world!\\end\n')

        output_path = dlb.fs.Path('build/out/')
        tex = dlb_contrib.tex.Tex(toplevel_file='report.tex', output_file=output_path / 'report.dvi', state_files=[])

        with dlb.ex.Context():
            r = tex.start()
            self.assertTrue(r)
            self.assertEqual((), r.included_files)
            self.assertTrue((output_path / 'report.dvi').native.raw.is_file())

            r = tex.start()
            self.assertFalse(r)


@unittest.skipUnless(testenv.has_executable_in_path('tex'), 'requires tex in $PATH')
class TexInputTest(testenv.TemporaryWorkingDirectoryTestCase):

    class RawTex(dlb.ex.Tool):
        EXECUTABLE = 'tex'

        toplevel_file = dlb.ex.input.RegularFile()
        stdout_file = dlb.ex.output.RegularFile()

        async def redo(self, result, context):
            arguments = [
                '-interaction=nonstopmode', '-halt-on-error', '-file-line-error', '-no-shell-escape',
                self.toplevel_file  # must be last
            ]
            await context.execute_helper(self.EXECUTABLE, arguments, stdout_output=self.stdout_file)

    def test_texpath_check_prevent_suspicious_filennames(self):
        top_file_name = 'top.tex'

        failure_on_commandline_by_character: Dict[str, str] = {}
        failure_on_input_by_character: Dict[str, str] = {}

        try:

            output = io.StringIO()
            dlb.di.set_output_file(output)

            with dlb.ex.Context():

                suspicious_characters = (
                    {chr(i) for i in range(1, 0x7F + 1)} -
                    set(string.ascii_letters) -
                    set(string.digits) -
                    {'/'}
                )

                for character in sorted(suspicious_characters):
                    with self.subTest(character=character):
                        input_filename = f'{character}{character}_{character}.tex'

                        with open(os.path.join('', input_filename), 'x', encoding='utf-8') as f:
                            f.write('Hello world!\\end\n')

                        with open(top_file_name, 'w', encoding='utf-8') as f:
                            f.write(f'\\input{{./{input_filename}}}\\end\n')

                        try:
                            tool = self.RawTex(
                                toplevel_file=input_filename,
                                stdout_file='stdout.log'
                            )
                            tool.start().complete()  # by command line
                        except dlb.ex.HelperExecutionError:
                            failure_on_commandline_by_character[character] = tool.stdout_file.native.read_text()

                        try:
                            tool = self.RawTex(
                                toplevel_file=top_file_name,
                                stdout_file='stdout.log'
                            )
                            tool.start().complete()  # by \input{...}
                        except dlb.ex.HelperExecutionError:
                            failure_on_input_by_character[character] = tool.stdout_file.native.read_text()

                        os.remove(input_filename)

                if character in failure_on_commandline_by_character or character in failure_on_input_by_character:
                    with self.assertRaises(ValueError):
                        dlb_contrib.tex.TexPath(input_filename)
                else:
                    dlb_contrib.tex.TexPath(input_filename)

            failed_by_input = set(failure_on_input_by_character.keys())
            failed_by_command_line = set(failure_on_commandline_by_character.keys())

            be_verbose = False

            try:
                self.assertTrue(failed_by_command_line.issubset(failed_by_input))

                # characters with default category code other than "space" (10), "letter" (11),
                # and "other character" (12)
                self.assertIn('\\', failed_by_input)  # "escape character" (0)
                self.assertIn('{', failed_by_input)  # "beginning of group" (1)
                self.assertIn('}', failed_by_input)  # "end of group" (2)
                self.assertIn('\r', failed_by_input)  # "end of line" (5)
                self.assertIn('#', failed_by_input)  # "parameter" (6)
                self.assertIn('~', failed_by_input)  # "active character" (13)
                self.assertIn('%', failed_by_input)  # "comment character" (14)
                self.assertIn('^', failed_by_input)  # "superscript" (7) - only disallowed if doubled
                self.assertIn('\x7F', failed_by_input)  # "invalid character" (15)

                # '&' and '_':
                # - fails for TeX 3.14159265 (TeX Live 2019/dev/Debian) kpathsea version 6.3.1/dev
                # - succeeds for TeX 3.14159265 (TeX Live 2020/Debian) kpathsea version 6.3.2

                # kpathsea:
                self.assertIn('\t', failed_by_input)
                self.assertIn('\n', failed_by_input)

                # '$':
                # - fails for TeX 3.14159265 (TeX Live 2019/dev/Debian) kpathsea version 6.3.1/dev
                # - succeeds for TeX 3.14159265 (TeX Live 2020/Debian) kpathsea version 6.3.2

                # web2c:
                self.assertIn('"', failed_by_input)
            except:
                be_verbose = True
                raise
            finally:
                if be_verbose:
                    for c in sorted(set(failed_by_input) | set(failed_by_command_line)):
                        print(f'failed {c!r}:')
                        failure_log_by_input = failure_on_input_by_character.get(c)
                        failure_log_by_commandline = failure_on_commandline_by_character.get(c)
                        if failure_log_by_input and c in failure_log_by_input:
                            print('    on \\input{...}:' +
                                  '\n        '.join([''] + failure_log_by_input.splitlines()))
                        if failure_log_by_commandline and c in failure_log_by_commandline:
                            print(
                                '    on command line:' +
                                '\n        '.join([''] + failure_log_by_commandline.splitlines()))

        finally:
            dlb.di.set_output_file(sys.stderr)


@unittest.skipUnless(testenv.has_executable_in_path('latex'), 'requires latex in $PATH')
class LatexTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_option_without_leading_dash(self):
        class Latex(dlb_contrib.tex.Tex):
            def get_options(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['-mltex', 'ahoi']

        open('report.tex', 'xb').close()
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                Latex(toplevel_file='report.tex', output_file='report.dvi', state_files=[]).start()
        self.assertEqual("not an option: 'ahoi'", str(cm.exception))

    def test_fails_for_non_existing_toplevel_file(self):
        open('report.txt.tex', 'xb').close()
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                dlb_contrib.tex.Tex(toplevel_file='report.txt', output_file='report.dvi', state_files=[]).start()
        msg = "input dependency 'toplevel_file' contains a path of a non-existent filesystem object: 'report.txt'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_missing_content(self):
        with open('report.tex', 'x', encoding='utf-8') as f:
            f.write('\\end')

        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                # does not create a .dvi
                dlb_contrib.tex.Tex(toplevel_file='report.tex', output_file='report.dvi', state_files=[]).start()

        self.assertRegex(str(cm.exception), r"\A()output file missing \(no pages\): .+")

    def test_fails_for_nonunique_statefile_suffix(self):
        open('report.tex', 'xb').close()
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                dlb_contrib.tex.Tex(toplevel_file='report.tex', output_file='report.dvi',
                                    state_files=['x.aux', 'y.aux']).start()
        msg = "'state_file' contains more than one path with suffix '.aux': 'x.aux', 'y.aux'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_lf_in_cwd(self):
        os.mkdir('out\nput')
        with testenv.DirectoryChanger('out\nput'):
            os.mkdir('.dlbroot')
            open('report.tex', 'xb').close()
            with self.assertRaises(Exception) as cm:
                with dlb.ex.Context():
                    dlb_contrib.tex.Tex(toplevel_file='report.tex', output_file='report.dvi', state_files=[]).start()
            self.assertEqual("current working directory must not contain '\\n'", str(cm.exception))

    def test_scenario1(self):
        os.mkdir('src')
        with open(os.path.join('src', 'report.tex'), 'x', encoding='utf-8') as f:
            f.write(
                '\\documentclass{article}\n'
                '\\begin{document}\n'
                '    \\tableofcontents\n'
                '    \\section{Greetings}\n'
                '    Hello \\input{"loc ation.tex"}!\n'
                '\\end{document}\n'
            )
        with open(os.path.join('src', 'loc ation.tex'), 'x', encoding='utf-8') as f:
            f.write('there')

        output_path = dlb.fs.Path('build/out/')
        latex = dlb_contrib.tex.Latex(
            toplevel_file='src/report.tex', output_file=output_path / 'report.dvi',
            input_search_directories=['src/'],
            state_files=[output_path / 'report.aux', output_path / 'report.toc']
        )

        with dlb.ex.Context():
            r = latex.start()
            self.assertTrue(r)
            self.assertEqual((dlb.fs.Path('src/loc ation.tex'),), r.included_files)
            self.assertTrue((output_path / 'report.aux').native.raw.is_file())
            self.assertTrue((output_path / 'report.toc').native.raw.is_file())

            r = latex.start()
            self.assertTrue(r)
            r = latex.start()
            self.assertFalse(r)

        with open(os.path.join('src', 'report.tex'), 'w', encoding='utf-8') as f:
            f.write(
                '\\documentclass{article}\n'
                '\\begin{document}\n'
                '    \\tableofcontents\n'
                '    \\section{Greetings}\n'
                '    \\subsection{Hello again}\n'
                '    Hello \\input{"loc ation.tex"}!\n'
                '\\end{document}\n'
            )
        with dlb.ex.Context():
            r = latex.start()
            self.assertTrue(r)
            r = latex.start()
            self.assertTrue(r)  # because index had been changed
            r = latex.start()
            self.assertFalse(r)

    def test_finds_file_in_texinputs(self):
        os.mkdir('src')
        with open(os.path.join('src', 'report.tex'), 'x', encoding='utf-8') as f:
            f.write(
                '\\documentclass{article}\n'
                '\\begin{document}\n'
                '    \\tableofcontents\n'
                '    \\section{Greetings}\n'
                '    Hello \\input{"loc ation.tex"}!\n'
                '\\end{document}\n'
            )
        with open(os.path.join('src', 'loc ation.tex'), 'x', encoding='utf-8') as f:
            f.write('there')

        output_path = dlb.fs.Path('build/out/')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('TEXINPUTS', pattern=r'.*', example='.:~/tex//:').set('../../../src/:')
            dlb_contrib.tex.Latex(
                toplevel_file='src/report.tex', output_file=output_path / 'report.dvi',
                intermediary_directory=output_path / 'latex/',
                state_files=[output_path / 'report.aux', output_path / 'report.toc']).start()

    def test_warns_for_missing_state_file(self):
        os.mkdir('src')
        with open(os.path.join('src', 'report.tex'), 'x', encoding='utf-8') as f:
            f.write(
                '\\documentclass{article}\n'
                '\\begin{document}\n'
                '    \\tableofcontents\n'
                '    \\section{Greetings}\n'
                '    Hello!\n'
                '\\end{document}\n'
            )

        output_path = dlb.fs.Path('build/out/')
        try:
            with dlb.ex.Context():
                output = io.StringIO()
                dlb.di.set_output_file(output)
                dlb_contrib.tex.Latex(toplevel_file='src/report.tex', output_file=output_path / 'report.dvi',
                                      state_files=[]).start()
            regex = (
                r"(?m).*\n"
                r"W 1 file\(s\) were read and written \(consider adding them to 'state_files'\): \n"
                r"  \| '\.dlbroot/t/a/report\.aux'\n\Z"
            )
            self.assertRegex(output.getvalue(), regex)
        finally:
            dlb.di.set_output_file(sys.stderr)

    def test_creates_log_on_error(self):
        os.mkdir('src')
        with open(os.path.join('src', 'report.tex'), 'x', encoding='utf-8') as f:
            f.write(
                '\\documentclass{article}\n'
                '\\begin{document}\n'
            )

        output_path = dlb.fs.Path('build/out/')
        log_file = output_path / 'report.log'

        try:
            with dlb.ex.Context():
                dlb.di.set_output_file(io.StringIO())
                dlb_contrib.tex.Latex(toplevel_file='src/report.tex', output_file=output_path / 'report.dvi',
                                      state_files=[], log_file=log_file).start()
        except dlb.ex.HelperExecutionError:
            pass

        self.assertTrue(log_file.native.raw.exists())

    def test_removes_log_file_before(self):
        os.mkdir('src')
        with open(os.path.join('src', 'report.tex'), 'x', encoding='utf-8') as f:
            f.write(
                '\\documentclass{article}\n'
                '\\begin{document}\n'
            )

        output_path = dlb.fs.Path('build/out/')
        log_file = output_path / 'report.log'
        output_path.native.raw.mkdir(parents=True)
        log_file.native.raw.touch()

        self.assertTrue(log_file.native.raw.exists())
        try:
            with dlb.ex.Context():
                dlb.ex.Context.active.helper[dlb_contrib.tex.Latex.EXECUTABLE] = output_path / 'non/existent'
                dlb.di.set_output_file(io.StringIO())
                dlb_contrib.tex.Latex(toplevel_file='src/report.tex', output_file=output_path / 'report.dvi',
                                      state_files=[], log_file=log_file).start()
        except FileNotFoundError:
            pass

        self.assertFalse(log_file.native.raw.exists())


@unittest.skipUnless(testenv.has_executable_in_path('tex'), 'requires tex in $PATH')
@unittest.skipUnless(testenv.has_executable_in_path('latex'), 'requires latex in $PATH')
class VersionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_version_is_string_with_dot(self):
        # noinspection PyPep8Naming
        Tools = [
            dlb_contrib.tex.Tex,
            dlb_contrib.tex.Latex,
        ]

        class QueryVersion(dlb_contrib.generic.VersionQuery):
            VERSION_PARAMETERS_BY_EXECUTABLE = {
                Tool.EXECUTABLE: Tool.VERSION_PARAMETERS
                for Tool in Tools
            }

        with dlb.ex.Context():
            version_by_path = QueryVersion().start().version_by_path
            self.assertEqual(len(QueryVersion.VERSION_PARAMETERS_BY_EXECUTABLE), len(version_by_path))
            for Tool in Tools:
                path = dlb.ex.Context.active.helper[Tool.EXECUTABLE]
                version = version_by_path[path]
                self.assertIsInstance(version, str)
                self.assertGreaterEqual(version.count('.'), 1)
