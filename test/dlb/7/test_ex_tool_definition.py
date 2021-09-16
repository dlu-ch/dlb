# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import sys
import os.path
import tempfile
import zipfile
import inspect
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class ToolDefinitionAmbiguityTest(testenv.TemporaryDirectoryTestCase):

    def test_location_in_zip_archive_package_is_normalized(self):  # os.path.altsep is replaced by os.path.sep
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
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname='u1/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname='u1/v.py')

            orig_getframeinfo = inspect.getframeinfo
            orig_altsep = os.path.altsep

            fake_altsep = os.path.altsep
            if fake_altsep is None:
                fake_altsep = '/' if os.path.altsep == '\\' else '\\'

            module_path_in_zip = f'{zip_file_path}{os.path.sep}u1{os.path.sep}v.py'
            fake_module_path_in_zip = f'{zip_file_path}{os.path.sep}u1{fake_altsep}v.py'

            def getframeinfo_except_zip_file_path(frame, context=1):
                f = orig_getframeinfo(frame, context)
                if f.filename != module_path_in_zip:
                    return f
                return inspect.Traceback(fake_module_path_in_zip, f.lineno, f.function, f.code_context, f.index)

            os.path.altsep = fake_altsep
            inspect.getframeinfo = getframeinfo_except_zip_file_path

            self.assertNotIn('dlb', sys.modules)
            import dlb.ex

            sys.path.insert(0, zip_file_path)
            try:
                # noinspection PyUnresolvedReferences
                import u1.v
            finally:
                os.path.altsep = orig_altsep
                inspect.getsourcefile = getframeinfo_except_zip_file_path
                del sys.path[0]

        self.assertEqual(u1.v.A.definition_location, (os.path.realpath(zip_file_path), os.path.join('u1', 'v.py'), 2))
