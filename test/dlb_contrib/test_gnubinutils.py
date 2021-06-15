# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.gcc
import dlb_contrib.gnubinutils
import os.path
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


@unittest.skipIf(not testenv.has_executable_in_path('gcc'), 'requires gcc in $PATH')
@unittest.skipIf(not testenv.has_executable_in_path('ar'), 'requires ar in $PATH')
class ArTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_example(self):
        with open('a.c', 'w') as f:
            f.write('int f() {return 0;}\n')
        with open('b.c', 'w') as f:
            f.write('int g() {return 0;}\n')

        import dlb.di
        import dlb.cf
        dlb.cf.level.helper_execution = dlb.di.ERROR

        with dlb.ex.Context():
            object_file_groups = [
                dlb_contrib.gcc.CCompilerGcc(source_files=[src_file],
                                             object_files=[src_file + '.o']).start().object_files
                for src_file in ['a.c', 'b.c']
            ]
            dlb_contrib.gnubinutils.Archive(object_files=[o for g in object_file_groups for o in g],
                                            archive_file='libexample.a').start()


@unittest.skipIf(not testenv.has_executable_in_path('ar'), 'requires ar in $PATH')
class VersionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_version_is_string_with_dot(self):
        # noinspection PyPep8Naming
        Tool = dlb_contrib.gnubinutils.Archive

        class QueryVersion(dlb_contrib.generic.VersionQuery):
            VERSION_PARAMETERS_BY_EXECUTABLE = {Tool.EXECUTABLE: Tool.VERSION_PARAMETERS}

        with dlb.ex.Context():
            version_by_path = QueryVersion().start().version_by_path
            path = dlb.ex.Context.active.helper[Tool.EXECUTABLE]
            self.assertEqual(1, len(version_by_path))
            version = version_by_path[path]
            self.assertIsInstance(version, str)
            self.assertGreaterEqual(version.count('.'), 2)
