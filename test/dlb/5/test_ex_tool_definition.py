# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import sys
import os.path
import tempfile
import zipfile
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class ToolDefinitionAmbiguityTest(testenv.TemporaryDirectoryTestCase):

    def test_fails_for_non_existing_source_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            with tempfile.TemporaryDirectory() as content_tmp_dir_path:
                open(os.path.join(content_tmp_dir_path, '__init__.py'), 'w').close()
                with open(os.path.join(content_tmp_dir_path, 'v.py'), 'w') as f:
                    f.write(
                        'import dlb.ex\n'
                        'class A(dlb.ex.Tool): pass'
                    )

                zip_file_path = os.path.join(tmp_dir_path, 'abc.zip')
                with zipfile.ZipFile(zip_file_path, 'w') as z:
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname='u2/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname='u2/v.py')

            sys.path.insert(0, zip_file_path)
            orig_isfile = os.path.isfile

            def isfile_except_zip_file_path(path):
                return False if path == zip_file_path else orig_isfile(path)

            os.path.isfile = isfile_except_zip_file_path
            try:
                # noinspection PyUnresolvedReferences
                with self.assertRaises(dlb.ex.DefinitionAmbiguityError) as cm:
                    import u2.v
            finally:
                os.path.isfile = orig_isfile
                del sys.path[0]

        msg = (
            "invalid tool definition: location of definition is unknown\n"
            "  | class: <class 'u2.v.A'>\n"
            "  | define the class in a regular file or in a zip archive ending in '.zip'\n"
            "  | note also the significance of upper and lower case of module search paths "
            "on case-insensitive filesystems"
        )
        self.assertEqual(msg, str(cm.exception))
