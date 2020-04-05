# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.ex
import dlb_contrib.gcc
import dlb_contrib.gnubinutils
import unittest
import tools_for_test


@unittest.skipIf(not os.path.isfile('/usr/bin/gcc'), 'requires gcc')
@unittest.skipIf(not os.path.isfile('/usr/bin/ar'), 'requires ar')
class ArTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_example(self):
        with open('a.c', 'w') as f:
            f.write('int f() {return 0;}\n')
        with open('b.c', 'w') as f:
            f.write('int g() {return 0;}\n')

        import dlb.cf
        import dlb.di
        dlb.cf.level.HELPER_EXECUTION = dlb.di.ERROR

        with dlb.ex.Context():
            object_files = [
                dlb_contrib.gcc.CCompilerGcc(source_file=src_file, object_file=src_file + '.o').run().object_file
                for src_file in ['a.c', 'b.c']
            ]
            dlb_contrib.gnubinutils.Archive(object_files=object_files, archive_file='libexample.a').run()
