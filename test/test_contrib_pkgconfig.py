# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib_pkgconfig
import unittest
from typing import Iterable, Union
import tools_for_test


class PkgConfigWithoutActualExecutionTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_empty_without_library_names(self):
        with dlb.ex.Context():
            r = dlb_contrib_pkgconfig.PkgConfig().run()
        self.assertEqual((), r.library_search_directories)
        self.assertEqual((), r.include_search_directories)

    def test_fails_for_invalid_library_name(self):
        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().run()

        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('-a',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().run()

        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('>a',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().run()

        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('<a',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().run()

        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a b',)

        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().run()

    def test_fails_for_invalid_version_constraint(self):
        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a',)
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'a': ''}
        with self.assertRaises(TypeError):
            with dlb.ex.Context():
                PkgConfig().run()

        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a',)
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'a': '= 1.2.3'}
        with self.assertRaises(TypeError):
            with dlb.ex.Context():
                PkgConfig().run()

        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a',)
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'a': ('>',)}
        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().run()

        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('a',)
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'a': ('=1.2.3',)}
        with self.assertRaises(ValueError):
            with dlb.ex.Context():
                PkgConfig().run()

    def test_parse(self):
        r = dlb_contrib_pkgconfig.parse_from_output('')
        self.assertEqual(({}, ()), r)

        line = '-pthread -I/usr/include/gtk-3.0 -I/usr/include/at-spi2-atk/2.0'
        r = dlb_contrib_pkgconfig.parse_from_output(line,)
        self.assertEqual(({}, ('-pthread', '-I/usr/include/gtk-3.0', '-I/usr/include/at-spi2-atk/2.0')), r)
        r = dlb_contrib_pkgconfig.parse_from_output(line, '-I')
        self.assertEqual(({'-I': ('/usr/include/gtk-3.0', '/usr/include/at-spi2-atk/2.0')}, ('-pthread',)), r)

        r = dlb_contrib_pkgconfig.parse_from_output('--libs abc')
        self.assertEqual(({}, ('--libs', 'abc')), r)


@unittest.skipIf(not os.path.isfile('/usr/bin/pkg-config'), 'requires pkg-config')
@unittest.skipIf(not os.path.isdir('/usr/include/gtk-3.0/'), 'requires GTK+ 3.0')
class PkgConfigTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_gtk(self):
        class PkgConfig(dlb_contrib_pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('gtk+-3.0', 'orte')
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'gtk+-3.0': ['> 3.0.1', '< 4.0']}

        with dlb.ex.Context():
            dlb.di.set_threshold_level(dlb.di.DEBUG)
            result = PkgConfig().run()

        self.assertIn('libgdk-3.so', result.library_filenames)
        self.assertIn(dlb.fs.Path('/usr/include/gtk-3.0/'), result.include_search_directories)
        self.assertEqual(('-pthread',), result.options)
