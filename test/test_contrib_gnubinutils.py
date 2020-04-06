# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import tools_for_test  # also sets up module search paths
import dlb.ex
import dlb_contrib.gcc
import dlb_contrib.gnubinutils
import os.path
import unittest


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
        dlb.cf.level.helper_execution = dlb.di.ERROR

        with dlb.ex.Context():
            object_file_groups = [
                dlb_contrib.gcc.CCompilerGcc(source_files=[src_file], object_files=[src_file + '.o']).run().object_files
                for src_file in ['a.c', 'b.c']
            ]
            dlb_contrib.gnubinutils.Archive(object_files=[o for g in object_file_groups for o in g],
                                            archive_file='libexample.a').run()
