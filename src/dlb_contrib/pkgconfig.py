# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Query paths of installed librares with pkg-config."""

import sys
import re
import subprocess
import collections.abc
import dlb.fs
import dlb.ex
assert sys.version_info >= (3, 7)

LIBRARY_NAME_REGEX = re.compile(r'^[A-Za-z_][^ \t\n\r]*$')
VERSION_CONSTRAINT_REGEX = re.compile('^(?P<comp>=|<|>|<=|>=) (?P<version>[A-za-z0-9_][^ \t\n\r]*)$')


def parse_from_output(line, options=''):  # parse an output line of pkg-config
    arguments_by_option = {}
    others = []
    for token in line.split(' '):
        if len(token) > 2 and token[0] == '-' and token[1] in options:
            k = token[:2]
            arguments_by_option[k] = arguments_by_option.get(k, ()) + (token[2:],)
        elif token:
            others.append(token)
    return arguments_by_option, tuple(others)


class PkgConfig(dlb.ex.Tool):
    # https://www.freedesktop.org/wiki/Software/pkg-config/
    EXECUTABLE = 'pkg-config'  # dynamic helper, looked-up in the context

    LIBRARY_NAMES = ()  # e.g. ('orte')

    LIBRARY_FILENAME_PATTERN = 'lib{}.so'

    # Optional version contraints for libraries in *LIBRARY_NAMES*
    #
    # Versions are compared component-wise; components are non-empty strings of alpha-numeric characters, separated
    # by non-empty strings of not-alphanumeric characters.
    # See here for definition of comparison: https://cgit.freedesktop.org/pkg-config/tree/rpmvercmp.c#n35.
    VERSION_CONSTRAINTS_BY_LIBRARY_NAME = {}  # e.g. {'orte': ('>= 1.2.3', '< 2.0')}

    # Duplicate-free tuple of library name to be searched in the library search directories and linked against.
    # Order matters; if library *b* depends on *a*, *b* should precede *a* in the sequence.
    # Each element has the form LIBRARY_FILENAME_PATTERN.format(n) with an appropriate *n*.
    # E.g. ('libgtk-3.so', 'libgdk-3.so').
    library_filenames = dlb.ex.Tool.Output.Object[:](explicit=False)

    # Duplicate-free tuple of paths of directories that are to be searched for libraries in addition to the standard
    # system directories in order to find all libraries in *library_filenames*.
    # E.g. (dlb.fs.Path('/usr/lib/x86_64-linux-gnu/openmpi/lib'),)
    library_search_directories = dlb.ex.Tool.Output.Object[:](explicit=False)

    # Duplicate-free tuple of paths of directories that are to be searched for include files in addition to the system
    # include files in order to find any of the include files of the libraries in *library_filenames*.
    # E.g. (dlb.fs.Path('/usr/include/gtk-3.0'),)
    include_search_directories = dlb.ex.Tool.Output.Object[:](explicit=False)

    # Options returned by pkg-config other than '-I...', '-L...', '-l...'.
    options = dlb.ex.Tool.Output.Object[:](explicit=False)

    async def redo(self, result, context):
        library_selection_arguments = []

        library_filenames = []
        library_search_directories = []
        include_search_directories = []
        options = []

        for lib in self.LIBRARY_NAMES:
            if not LIBRARY_NAME_REGEX.match(lib):
                raise ValueError(f"invalid library name: {lib!r}")
            contraints = self.VERSION_CONSTRAINTS_BY_LIBRARY_NAME.get(lib)
            if contraints is None:
                library_selection_arguments.append(lib)
            else:
                if not isinstance(contraints, collections.abc.Sequence) or isinstance(contraints, (str, bytes)):
                    msg = (
                        f"version constraint for library {lib!r} is not a sequence "
                        f"other than str and bytes: {contraints!r}"
                    )
                    raise TypeError(msg)
                for c in contraints:
                    m = VERSION_CONSTRAINT_REGEX.match(c)
                    if not m:
                        raise ValueError(f"invalid version constraint for library {lib!r}: {c!r}")
                    library_selection_arguments.append(f'{lib} {c}')

        if library_selection_arguments:
            _, stdout, _ = await context.execute_helper(
                self.EXECUTABLE, ['--cflags', '--libs'] + library_selection_arguments,
                stdout=subprocess.PIPE)
            arguments_by_option, options = parse_from_output(stdout.decode().strip(), options='ILl')

            for p in arguments_by_option.get('-I', []):
                p = dlb.fs.Path(dlb.fs.Path.Native(p), is_dir=True)
                if p not in include_search_directories:
                    include_search_directories.append(p)

            for p in arguments_by_option.get('-L', []):
                p = dlb.fs.Path(dlb.fs.Path.Native(p), is_dir=True)
                if p not in library_search_directories:
                    library_search_directories.append(p)

            for n in arguments_by_option.get('-l', []):
                n = self.LIBRARY_FILENAME_PATTERN.format(n)
                if n not in library_filenames:
                    library_filenames.append(n)

        result.library_filenames = library_filenames
        result.library_search_directories = library_search_directories
        result.include_search_directories = include_search_directories
        result.options = options

        return True
