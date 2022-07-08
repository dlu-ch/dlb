# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import sys
import os.path
import tempfile
import zipfile
import inspect
import importlib
import unittest

import dlb.ex


class ThisIsAUnitTest(unittest.TestCase):
    pass


class ToolDefinitionAmbiguityTest(testenv.TemporaryDirectoryTestCase):

    def test_fails_for_non_existing_source_file(self):
        module_name = 'single_use_module1'
        self.assertNotIn(module_name, sys.modules)  # needs a name different from all already loaded modules

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
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname=f'{module_name}/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname=f'{module_name}/v.py')

            importlib.invalidate_caches()
            sys.path.insert(0, zip_file_path)
            orig_isfile = os.path.isfile

            def isfile_except_zip_file_path(path):
                return False if os.path.realpath(path) == os.path.realpath(zip_file_path) else orig_isfile(path)

            os.path.isfile = isfile_except_zip_file_path
            try:
                # noinspection PyUnresolvedReferences
                with self.assertRaises(dlb.ex.DefinitionAmbiguityError) as cm:
                    import single_use_module1.v
            finally:
                os.path.isfile = orig_isfile
                del sys.path[0]

        msg = (
            f"invalid tool definition: location of definition is unknown\n"
            f"  | class: <class '{module_name}.v.A'>\n"
            f"  | define the class in a regular file or in a zip archive ending in '.zip'\n"
            f"  | note also the significance of upper and lower case of module search paths "
            f"on case-insensitive filesystems"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_location_in_zip_archive_package_is_normalized(self):  # os.path.altsep is replaced by os.path.sep
        module_name = 'single_use_module2'
        self.assertNotIn(module_name, sys.modules)  # needs a name different from all already loaded modules

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
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname=f'{module_name}/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname=f'{module_name}/v.py')

            orig_getframeinfo = inspect.getframeinfo
            orig_altsep = os.path.altsep

            fake_altsep = os.path.altsep
            if fake_altsep is None:
                fake_altsep = '/' if os.path.altsep == '\\' else '\\'

            module_path_in_zip = f'{zip_file_path}{os.path.sep}{module_name}{os.path.sep}v.py'
            fake_module_path_in_zip = f'{zip_file_path}{os.path.sep}{module_name}{fake_altsep}v.py'

            def getframeinfo_except_zip_file_path(frame, context=1):
                f = orig_getframeinfo(frame, context)
                if f.filename != module_path_in_zip:
                    return f
                return inspect.Traceback(fake_module_path_in_zip, f.lineno, f.function, f.code_context, f.index)

            os.path.altsep = fake_altsep
            inspect.getframeinfo = getframeinfo_except_zip_file_path

            importlib.invalidate_caches()
            sys.path.insert(0, zip_file_path)
            try:
                # noinspection PyUnresolvedReferences
                import single_use_module2.v
            finally:
                os.path.altsep = orig_altsep
                inspect.getsourcefile = getframeinfo_except_zip_file_path
                del sys.path[0]

        self.assertEqual((os.path.realpath(zip_file_path), os.path.join(module_name, 'v.py'), 2),
                         single_use_module2.v.A.definition_location)
