# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.di
import dlb.fs
import dlb.ex
import dlb_contrib.generic
import dlb_contrib.pkgconfig
import os.path
import shutil
import unittest
from typing import Iterable, Union


class ThisIsAUnitTest(unittest.TestCase):
    pass


class PkgConfigWithoutActualExecutionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_empty_without_library_names(self):
        with dlb.ex.Context():
            r = dlb_contrib.pkgconfig.PkgConfig().start()
        self.assertEqual((), r.library_search_directories)
        self.assertEqual((), r.include_search_directories)

    def test_fails_for_invalid_library_name(self):
        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().start()

        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('-a',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().start()

        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('>a',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().start()

        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('<a',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().start()

        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a b',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().start()

    def test_fails_for_invalid_version_constraint(self):
        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a',)
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'a': ''}
        with self.assertRaises(TypeError):
            with dlb.ex.Context():
                PkgConfig().start()

        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a',)
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'a': '= 1.2.3'}
        with self.assertRaises(TypeError):
            with dlb.ex.Context():
                PkgConfig().start()

        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a',)
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'a': ('>',)}
        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().start()

        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a',)
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'a': ('=1.2.3',)}
        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().start()

    def test_parse(self):
        r = dlb_contrib.pkgconfig.parse_from_output('')
        self.assertEqual(({}, ()), r)

        line = '-pthread -I/usr/include/gtk-3.0 -I/usr/include/at-spi2-atk/2.0'
        r = dlb_contrib.pkgconfig.parse_from_output(line,)
        self.assertEqual(({}, ('-pthread', '-I/usr/include/gtk-3.0', '-I/usr/include/at-spi2-atk/2.0')), r)
        r = dlb_contrib.pkgconfig.parse_from_output(line, '-I')
        self.assertEqual(({'-I': ('/usr/include/gtk-3.0', '/usr/include/at-spi2-atk/2.0')}, ('-pthread',)), r)

        r = dlb_contrib.pkgconfig.parse_from_output('--libs abc')
        self.assertEqual(({}, ('--libs', 'abc')), r)


@unittest.skipIf(not shutil.which('pkg-config'), 'requires pkg-config in $PATH')
@unittest.skipIf(not os.path.isdir('/usr/include/gtk-3.0/'), 'requires GTK+ 3.0')
class PkgConfigTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_gtk(self):
        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('gtk+-3.0', 'orte')
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'gtk+-3.0': ['> 3.0.1', '< 4.0']}

        with dlb.ex.Context():
            dlb.di.set_threshold_level(dlb.di.DEBUG)
            result = PkgConfig().start()

        self.assertIn('libgdk-3.so', result.library_filenames)
        self.assertIn(dlb.fs.Path('/usr/include/gtk-3.0/'), result.include_search_directories)
        self.assertEqual(('-pthread',), result.other_options)


@unittest.skipIf(not shutil.which('pkg-config'), 'requires pkg-config in $PATH')
class VersionTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_version_is_string_with_dot(self):
        # noinspection PyPep8Naming
        Tool = dlb_contrib.pkgconfig.PkgConfig

        class QueryVersion(dlb_contrib.generic.VersionQuery):
            VERSION_PARAMETERS_BY_EXECUTABLE = {Tool.EXECUTABLE: Tool.VERSION_PARAMETERS}

        with dlb.ex.Context():
            version_by_path = QueryVersion().start().version_by_path
            path = dlb.ex.Context.active.helper[Tool.EXECUTABLE]
            self.assertEqual(1, len(version_by_path))
            version = version_by_path[path]
            self.assertIsInstance(version, str)
            self.assertGreaterEqual(version.count('.'), 1)
