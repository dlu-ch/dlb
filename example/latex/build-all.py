# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

# Run this script by one of the following shell commands:
#
#    dlb build-all                  # from anywhere in the working tree (with directory of 'dlb' in $PATH)
#    python3 -m build-all           # in the directory of this file
#    python3 "$PWD"/build-all.py'   # in the directory of this file

import sys

import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.tex
import dlb_contrib.iso6429


if sys.stderr.isatty():
    # assume ISO/IEC 6429 conformant terminal ("VT-100 compatible")
    dlb.di.set_output_file(dlb_contrib.iso6429.MessageColorator(sys.stderr))


class PdfLatex(dlb_contrib.tex.Latex):
    EXECUTABLE = 'pdflatex'
    OUTPUT_EXTENSION = 'pdf'


with dlb.ex.Context():
    source_directory = dlb.fs.Path('src/')
    output_directory = dlb.fs.Path('build/out/')

    # repeat redo until all state files exist and their content remains unchanged, but at most 10 times
    for i in range(10):
        r = PdfLatex(toplevel_file='src/report.tex',
                     output_file=output_directory / 'report.pdf',
                     input_search_directories=['src/'],
                     state_files=[output_directory / 'report.aux', output_directory / 'report.toc']).run()
        if not r:
            break
