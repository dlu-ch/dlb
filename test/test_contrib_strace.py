# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import tools_for_test  # also sets up module search paths
import dlb.fs
import dlb.di
import dlb.ex
import dlb_contrib.strace
import os.path
import unittest
from typing import Tuple, List, Iterable, Union


class RegexTest(unittest.TestCase):

    def test_quoted_string(self):
        self.assertTrue(dlb_contrib.strace.QUOTED_STRING_ARG_REGEX.fullmatch(b'""'))
        self.assertTrue(dlb_contrib.strace.QUOTED_STRING_ARG_REGEX.fullmatch(b'"a\\nc"'))
        self.assertTrue(dlb_contrib.strace.QUOTED_STRING_ARG_REGEX.fullmatch(b'"a\\\\c"'))
        self.assertFalse(dlb_contrib.strace.QUOTED_STRING_ARG_REGEX.fullmatch(b'"a\\"'))
        self.assertFalse(dlb_contrib.strace.QUOTED_STRING_ARG_REGEX.fullmatch(b'"""'))


class ParseLineTest(unittest.TestCase):

    def test_successful_read_is_correct(self):
        line = (
            rb'read(3</lib/x86_64-linux-gnu/libc-2.28.so>, '
            rb'"\177ELF\2\1\1\3\0\0\0\0\0\0\0\0\3\0>\0\1\0\0\0\260A\2\0\0\0\0\0"..., 832) = 832'
        )
        name, potential_filesystem_paths, other_arguments, value = dlb_contrib.strace.syscall_from_line(line)
        self.assertEqual('read', name)
        self.assertEqual(['/lib/x86_64-linux-gnu/libc-2.28.so'], potential_filesystem_paths)
        self.assertEqual([rb'"\177ELF\2\1\1\3\0\0\0\0\0\0\0\0\3\0>\0\1\0\0\0\260A\2\0\0\0\0\0"...', b'832'],
                         other_arguments)
        self.assertEqual(b'832', value)

    def test_successful_write_is_correct(self):
        line = rb'write(1</tm\n\"p/empty>, "\n", 1) = 1'
        name, potential_filesystem_paths, other_arguments, value = dlb_contrib.strace.syscall_from_line(line)
        self.assertEqual('write', name)
        self.assertEqual(['/tm\n"p/empty', '\n'], potential_filesystem_paths)
        self.assertEqual([b'1'], other_arguments)
        self.assertEqual(b'1', value)

    def test_successful_write_with_undecodable_path_is_correct(self):
        line = b'write(1</t\377p/empty>, "\\n", 1) = 1'
        name, potential_filesystem_paths, other_arguments, value = dlb_contrib.strace.syscall_from_line(line)
        self.assertEqual('write', name)
        self.assertEqual([None, '\n'], potential_filesystem_paths)
        self.assertEqual([b'1'], other_arguments)
        self.assertEqual(b'1', value)

    def test_successful_execve_is_correct(self):
        line = rb'execve("/bin/cat", ["cat", "empty"], 0x7fffb28622d0 /* 39 vars */) = 0'
        name, potential_filesystem_paths, other_arguments, value = dlb_contrib.strace.syscall_from_line(line)
        self.assertEqual('execve', name)
        self.assertEqual(['/bin/cat'], potential_filesystem_paths)
        self.assertEqual([b'["cat", "empty"]', b'0x7fffb28622d0 /* 39 vars */'], other_arguments)
        self.assertEqual(b'0', value)

    def test_successful_stat_is_correct(self):
        line = rb'stat("/tmp/strace", {st_mode=S_IFDIR|0755, st_size=12288, ...}) = 0'
        name, potential_filesystem_paths, other_arguments, value = dlb_contrib.strace.syscall_from_line(line)
        self.assertEqual('stat', name)
        self.assertEqual(['/tmp/strace'], potential_filesystem_paths)
        self.assertEqual([b'{st_mode=S_IFDIR|0755, st_size=12288, ...}'], other_arguments)
        self.assertEqual(b'0', value)

    def test_failed_stat_is_correct(self):
        line = rb'stat("/usr/local/bin/bash", 0x7ffe3ab307f0) = -1 ENOENT (Datei oder Verzeichnis nicht gefunden)'
        name, potential_filesystem_paths, other_arguments, value = dlb_contrib.strace.syscall_from_line(line)
        self.assertEqual('stat', name)
        self.assertEqual(['/usr/local/bin/bash'], potential_filesystem_paths)
        self.assertEqual([b'0x7ffe3ab307f0'], other_arguments)
        self.assertEqual(b'-1 ENOENT (Datei oder Verzeichnis nicht gefunden)', value)

    def test_fails_without_closing_parenthesis(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.strace.syscall_from_line(b'read(1,')
        msg = "missing ')' in argument list"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.strace.syscall_from_line(b'read(1, 3')
        msg = "missing ')' in argument list"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.strace.syscall_from_line(b'read(1, [1, 2) = 4')
        msg = "missing ']' in argument list"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb_contrib.strace.syscall_from_line(b'read(1, {1, 2) = 4')
        msg = "missing '}' in argument list"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_invalid_argument(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.strace.syscall_from_line(b'read(1, ])')
        msg = "invalid argument: b'])'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_invalid_quoting(self):
        with self.assertRaises(ValueError) as cm:
            dlb_contrib.strace.syscall_from_line(b'read(1, "\\xZ")')
        msg = "invalid quoting in argument: b'\"\\\\xZ\"'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_invalid_name(self):
        with self.assertRaises(ValueError):
            dlb_contrib.strace.syscall_from_line(b'123() = 0')

    def test_fails_without_opening_parenthesis(self):
        with self.assertRaises(ValueError):
            dlb_contrib.strace.syscall_from_line(b'read')

    def test_fails_without_return_value(self):
        with self.assertRaises(ValueError):
            dlb_contrib.strace.syscall_from_line(b'read(1, 3)')

    def test_fails_for_empty(self):
        with self.assertRaises(ValueError):
            dlb_contrib.strace.syscall_from_line(b'')


@unittest.skipIf(not os.path.isfile('/usr/bin/strace'), 'requires strace')
@unittest.skipIf(not os.path.isfile('/bin/bash'), 'requires bash')
@unittest.skipIf(not os.path.isfile('/bin/cat'), 'requires cat')
@unittest.skipIf(not os.path.isfile('/bin/cp'), 'requires cp')
class RunStracedTest(tools_for_test.TemporaryWorkingDirectoryTestCase):

    def test_discovers_read_files(self):
        with open('x', 'xb') as f:
            f.write(b'abc')
        with open('y', 'xb') as f:
            f.write(b'')

        class ShowContent(dlb_contrib.strace.RunStraced):
            EXECUTABLE = 'bash'

            def get_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return ['-c', '-', 'cat  -- *', 's']

        with dlb.ex.Context():
            r = ShowContent().run()
        self.assertEqual((dlb.fs.Path('x'), dlb.fs.Path('y')), r.read_files)

    def test_discovers_written_files(self):
        import typing

        with open('x', 'xb') as f:
            f.write(b'abc')

        class ShowContent(dlb_contrib.strace.RunStraced):
            EXECUTABLE = 'cp'

            source_file = dlb.ex.Tool.Input.RegularFile()
            target_file = dlb.ex.Tool.Output.RegularFile()

            def get_arguments(self) -> Iterable[Union[str, dlb.fs.Path, dlb.fs.Path.Native]]:
                return [self.source_file, self.target_file]

        with dlb.ex.Context():
            r = ShowContent(source_file='x', target_file='y').run()
        self.assertEqual((dlb.fs.Path('x'),), r.read_files)
        self.assertEqual((dlb.fs.Path('y'),), r.written_files)
