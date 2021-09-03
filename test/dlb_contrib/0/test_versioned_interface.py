# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.ex
import dlb_contrib.versioned_interface
import os.path
import os
import hashlib
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class CheckHashTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_scenario1(self):
        with open('x.h', 'xb') as f:
            f.write(b'int sum(int x, int y);\n')
        with open('y.h', 'xb') as f:
            f.write(b'int triple(int x);\n')

        with open('version.h', 'xb') as f:
            f.write(
                b'// last checked for header file hash 8f7df260a708db84f8f9c3fda6190e5ec16f02a8\n'
                b'// (use <none> for hash to disable check temporarily\n'
                b'#define LIBX_API_VERSION 2\n'
            )

        dlb_contrib.versioned_interface.check_hash(
            files_to_hash=[dlb.fs.Path('x.h'), 'y.h'],
            hash_line_file='version.h',
            hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
            warnonly_hash=b'<none>'
        )

        # changing a .h lets check fail
        with open('y.h', 'wb') as f:
            f.write(b'float triple(float x);\n')
        with self.assertRaises(dlb_contrib.versioned_interface.HashMismatch) as cm:
            dlb_contrib.versioned_interface.check_hash(
                files_to_hash=(p for p in ['x.h', 'y.h']),
                hash_line_file=dlb.fs.Path('version.h'),
                hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
                warnonly_hash=b'<none>'
            )
        msg = (
            "check and update the version information or the hash line:\n"
            "  | in 'version.h'\n"
            "  | replace the line '// last checked for header file hash 8f7df260a708db84f8f9c3fda6190e5ec16f02a8'\n"
            "  | by '// last checked for header file hash 05169ab311a1e1231c50fa0b490cb511dde0d86b'"
        )
        self.assertEqual(msg, str(cm.exception))

        with open('version.h', 'wb') as f:
            f.write(
                b'// last checked for header file hash 05169ab311a1e1231c50fa0b490cb511dde0d86b\n'
                b'// (use <none> for hash to disable check temporarily\n'
                b'#define LIBX_API_VERSION 2\n'
            )
        dlb_contrib.versioned_interface.check_hash(
            files_to_hash=[dlb.fs.Path('x.h'), 'y.h'],
            hash_line_file='version.h',
            hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
            warnonly_hash=b'<none>'
        )

        # changing a version file lets check fail
        with open('version.h', 'wb') as f:
            f.write(
                b'// last checked for header file hash 05169ab311a1e1231c50fa0b490cb511dde0d86b\n'
                b'// (use <none> for hash to disable check temporarily\n'
                b'#define LIBX_API_VERSION 3\n')
        with self.assertRaises(dlb_contrib.versioned_interface.HashMismatch) as cm:
            dlb_contrib.versioned_interface.check_hash(
                files_to_hash=['x.h', 'y.h'],
                hash_line_file='version.h',
                hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
                warnonly_hash=b'<none>'
            )
        msg = (
            "check and update the version information or the hash line:\n"
            "  | in 'version.h'\n"
            "  | replace the line '// last checked for header file hash 05169ab311a1e1231c50fa0b490cb511dde0d86b'\n"
            "  | by '// last checked for header file hash 90c649538a8f97c7b4f80d84b6ae204ce2e205d7'"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fail_for_missing_hash_line(self):
        open('version.h', 'x').close()

        with self.assertRaises(dlb_contrib.versioned_interface.HashLineFileError) as cm:
            dlb_contrib.versioned_interface.check_hash(
                files_to_hash=[],
                hash_line_file='version.h',
                hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
            )
        self.assertEqual("'version.h' contains no hash line", str(cm.exception))

    def test_fail_for_multiple_hash_line(self):
        with open('version.h', 'wb') as f:
            f.write(
                b'// last checked for header file hash 05169ab311a1e1231c50fa0b490cb511dde0d86b\n'
                b'// last checked for header file hash 90c649538a8f97c7b4f80d84b6ae204ce2e205d7\n'
            )

        with self.assertRaises(dlb_contrib.versioned_interface.HashLineFileError) as cm:
            dlb_contrib.versioned_interface.check_hash(
                files_to_hash=[],
                hash_line_file='version.h',
                hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
            )
        self.assertEqual("'version.h' contains more than one hash line", str(cm.exception))

    def test_hash_line_file_is_hashed_like_other(self):
        with open('version.h', 'wb') as f:
            f.write(
                b'aha!\r\n'
                b'// last checked for header file hash 90c649538a8f97c7b4f80d84b6ae204ce2e205d7\n'
                b'soso...\r'
            )

        content_without_hashline = (
            b'aha!\r\n'
            b'soso...\r'
        )
        self.assertEqual('82b46457c459c7aabae8ce76a040bc99cba93e64', hashlib.sha1(content_without_hashline).hexdigest())

        with self.assertRaises(dlb_contrib.versioned_interface.HashMismatch) as cm:
            dlb_contrib.versioned_interface.check_hash(
                files_to_hash=[],
                hash_line_file='version.h',
                hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
            )
        msg = (
            "check and update the version information or the hash line:\n"
            "  | in 'version.h'\n"
            "  | replace the line '// last checked for header file hash 90c649538a8f97c7b4f80d84b6ae204ce2e205d7'\n"
            "  | by '// last checked for header file hash 82b46457c459c7aabae8ce76a040bc99cba93e64'"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_warns_for_hash_to_ignore(self):
        with open('version.h', 'wb') as f:
            f.write(
                b'aha!\r\n'
                b'// last checked for header file hash <none>\n'
                b'soso...\r'
            )

        with self.assertWarns(UserWarning) as cm:
            dlb_contrib.versioned_interface.check_hash(
                files_to_hash=[],
                hash_line_file='version.h',
                hash_line_regex=rb'^// last checked for header file hash ([0-9a-f]+|<none>)$',
                warnonly_hash=b'<none>'
            )
        self.assertEqual("comparison of hash line disabled (do this only temporarily)", str(cm.warning))
