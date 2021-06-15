# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.tex
import sys
import os.path
import shutil
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

    def test_fails_for_separators(self):
        for c in ' ,;:':
            with self.assertRaises(ValueError):
                dlb_contrib.tex.KpathseaPath(f'a{c}b')

    def test_fails_for_variable(self):
        for c in '${}':
            with self.assertRaises(ValueError):
                dlb_contrib.tex.KpathseaPath(f'a{c}b')


class TexPathTest(unittest.TestCase):

    def test_fails_for_lineseparator(self):
        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexPath('a\nb.tex')

        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexPath('a\rb.tex')

    def test_fails_without_suffix(self):

        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexPath('document')

        with self.assertRaises(ValueError):
            dlb_contrib.tex.TexPath('.document')


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


@unittest.skipIf(not shutil.which('latex'), 'requires latex in $PATH')
class LatexTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_missing_extension(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            dlb_contrib.tex.Tex(toplevel_file='report', output_file='report.dvi', state_files=[])
        msg = (
            "keyword argument for dependency role 'toplevel_file' is invalid: 'report'\n"
            "  | reason: invalid path for 'TexPath': 'report' (must contain '.')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_option_without_leading_dash(self):
        class Latex(dlb_contrib.tex.Tex):
            def get_options(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['-mltex', 'ahoi']

        open('report.tex', 'xb').close()
        with self.assertRaises(ValueError) as cm:
            with dlb.ex.Context():
                Latex(toplevel_file='report.tex', output_file='report.dvi', state_files=[]).start()
        self.assertEqual("not an option: 'ahoi'", str(cm.exception))

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
            dlb.ex.Context.active.env.import_from_outer('TEXINPUTS', pattern=r'.*', example='.:~/tex//:')
            dlb.ex.Context.active.env['TEXINPUTS'] = '../../../src/:'
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


@unittest.skipIf(not shutil.which('tex'), 'requires tex in $PATH')
@unittest.skipIf(not shutil.which('latex'), 'requires latex in $PATH')
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
