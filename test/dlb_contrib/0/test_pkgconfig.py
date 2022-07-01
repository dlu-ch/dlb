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


@unittest.skipUnless(testenv.has_executable_in_path('pkg-config'), 'requires pkg-config in $PATH')
class PkgConfigTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_faked_gtk_and_orte(self):
        # from /usr/lib/x86_64-linux-gnu/pkgconfig/gtk+-3.0.pc of Debian GNU/Linux 10.12,
        # requirements reduced/renamed, comments and empty lines removed:
        with open('fake-gtk+-3.0.pc', 'xb') as f:
            f.write(
                b'prefix=/usr\n'
                b'exec_prefix=${prefix}\n'
                b'libdir=/usr/lib/x86_64-linux-gnu\n'
                b'includedir=${prefix}/include\n'
                b'targets=x11 broadway wayland\n'
                b'gtk_binary_version=3.0.0\n'
                b'gtk_host=x86_64-pc-linux-gnu\n'
                b'Name: GTK+\n'
                b'Description: GTK+ Graphical UI Library\n'
                b'Version: 3.24.5\n'
                b'Requires: fake-gdk-3.0\n'
                b'Libs: -L${libdir} -lgtk-3 \n'
                b'Cflags: -I${includedir}/gtk-3.0\n' 
            )

        with open('fake-gdk-3.0.pc', 'xb') as f:
            # from /usr/lib/x86_64-linux-gnu/pkgconfig/gdk-3.0.pc of Debian GNU/Linux 10.12,
            # requirements, comments, and empty lines removed:
            f.write(
                b'prefix=/usr\n'
                b'exec_prefix=${prefix}\n'
                b'libdir=/usr/lib/x86_64-linux-gnu\n'
                b'includedir=${prefix}/include\n'
                b'targets=x11 broadway wayland\n'
                b'Name: GDK\n'
                b'Description: GTK+ Drawing Kit\n'
                b'Version: 3.24.5\n'
                b'Libs: -L${libdir} -lgdk-3\n'
                b'Cflags: -I${includedir}/gtk-3.0\n'
            )

        with open('fake-orte.pc', 'xb') as f:
            # from /usr/lib/x86_64-linux-gnu/pkgconfig/orte.pc of Debian GNU/Linux 10.12,
            # requirements, comments, and empty lines removed:
            f.write(
                b"Name: Open MPI Run-Time Environment (ORTE)\n"
                b"Description: Open MPI's run-time environment functionality\n"
                b"Version: 3.1.3\n"
                b"URL: http://www.open-mpi.org/\n"
                b"prefix=/usr\n"
                b"exec_prefix=${prefix}\n"
                b"includedir=${prefix}/lib/x86_64-linux-gnu/openmpi/include\n"
                b"libdir=${prefix}/lib/x86_64-linux-gnu/openmpi/lib\n"
                b"pkgincludedir=${includedir}/openmpi\n"
                b"Libs: -L${libdir} -lopen-rte\n"
                b"Libs.private: -lopen-pal -lhwloc -ldl -levent -levent_pthreads -lutil -lm\n" 
                b"Cflags: -I${includedir} -I${includedir}/openmpi -pthread\n"
            )

        class PkgConfig(dlb_contrib.pkgconfig.PkgConfig):
            LIBRARY_NAMES = ('fake-gtk+-3.0', 'fake-orte')
            VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {'fake-gtk+-3.0': ['> 3.0.1', '< 4.0']}

        with dlb.ex.Context():
            dlb.di.set_threshold_level(dlb.di.DEBUG)
            dlb.ex.Context.active.env.import_from_outer('PKG_CONFIG_PATH', pattern='.+', example='/a/b:/c')
            dlb.ex.Context.active.env['PKG_CONFIG_PATH'] = '.'
            result = PkgConfig().start()

        self.assertIn('libgdk-3.so', result.library_filenames)
        self.assertIn(dlb.fs.Path('/usr/include/gtk-3.0/'), result.include_search_directories)
        self.assertEqual(('-pthread',), result.other_options)


@unittest.skipUnless(testenv.has_executable_in_path('pkg-config'), 'requires pkg-config in $PATH')
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
