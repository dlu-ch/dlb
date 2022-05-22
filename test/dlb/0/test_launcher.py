# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb_launcher
import dlb
import sys
import os.path
import re
import io
import pathlib
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class FindWorkingtreeRootTest(testenv.CommandlineToolTestCase,
                              testenv.TemporaryWorkingDirectoryTestCase):

    def test_chdir_stays_in_workingtree_root(self):
        root = os.getcwd()
        r = dlb_launcher.main()
        self.assertEqual(2, r)
        self.assertEqual(root, os.getcwd())

    def test_does_chdir_up_to_workingtree_root(self):
        root = os.getcwd()
        os.makedirs(os.path.join('a', 'b', 'c'))
        os.chdir(os.path.join('a', 'b', 'c'))
        self.assertNotEqual(root, os.getcwd())
        r = dlb_launcher.main()
        self.assertEqual(2, r)
        self.assertEqual(root, os.getcwd())

    def test_fails_outside_workingtree(self):
        os.chdir(pathlib.Path.cwd().anchor)
        root = os.getcwd()
        r = dlb_launcher.main()
        self.assertEqual(1, r)
        msg = "error: current working directory not in a dlb working tree (no '.dlbroot' found)\n"
        self.assertEqual(msg, sys.stderr.getvalue())
        self.assertEqual(root, os.getcwd())


class HelpTest(testenv.CommandlineToolTestCase,
               testenv.TemporaryWorkingDirectoryTestCase):

    documentation_url = 'https://dlb.readthedocs.io/'

    def test_displays_help_inside_working_tree(self):
        sys.argv = [sys.argv[0]] + ['--help']
        r = dlb_launcher.main()
        self.assertEqual(0, r)
        regex = r"(?s)\A()Run a dlb script .*\.\n\Z"
        self.assertRegex(sys.stdout.getvalue(), regex)

    def test_displays_help_outside_working_tree(self):
        os.chdir(pathlib.Path.cwd().anchor)
        sys.argv = [sys.argv[0]] + ['--help']
        r = dlb_launcher.main()
        self.assertEqual(0, r)
        regex = r"(?s)\A()Run a dlb script .*\.\n\Z"
        self.assertRegex(sys.stdout.getvalue(), regex)

    def test_help_lines_are_short(self):
        sys.argv = [sys.argv[0]] + ['--help']
        r = dlb_launcher.main()
        self.assertEqual(0, r)
        lines = sys.stdout.getvalue().split('\n')
        self.assertLessEqual(max(len(li) for li in lines), 80)

    def test_help_includes_version(self):
        sys.argv = [sys.argv[0]] + ['--help']
        r = dlb_launcher.main()
        self.assertEqual(0, r)
        regex = r'.*\ndlb version: {}.\n'.format(re.escape(dlb.__version__))
        self.assertRegex(sys.stdout.getvalue(), regex)

    def test_help_includes_documentation_url(self):
        sys.argv = [sys.argv[0]] + ['--help']
        r = dlb_launcher.main()
        self.assertEqual(0, r)
        regex = r'.*\nFull documentation at: <{}.*>.\n'.format(re.escape(self.documentation_url))
        self.assertRegex(sys.stdout.getvalue(), regex)

    def test_help_includes_documentation_url_for_released_version(self):
        version = dlb.__version__
        version_info = dlb.version_info

        try:
            dlb.__version__ = '1.2.3'
            dlb.version_info = (1, 2, 3)
            sys.argv = [sys.argv[0]] + ['--help']
            r = dlb_launcher.main()
            self.assertEqual(0, r)
            regex = r'.*\nFull documentation at: <{}.*>.\n'.format(re.escape(self.documentation_url + 'en/v1.2.3'))
            self.assertRegex(sys.stdout.getvalue(), regex)
        finally:
            dlb.__version__ = version
            dlb.version_info = version_info

    def test_help_includes_documentation_url_for_unreleased_version(self):
        version = dlb.__version__
        version_info = dlb.version_info

        try:
            dlb.__version__ = '1.2.3c4'
            dlb.version_info = (1, 2, 3, 'c', 4)
            sys.argv = [sys.argv[0]] + ['--help']
            r = dlb_launcher.main()
            self.assertEqual(0, r)
            regex = r'.*\nFull documentation at: <{}.*>.\n'.format(re.escape(self.documentation_url))
            self.assertRegex(sys.stdout.getvalue(), regex)
        finally:
            dlb.__version__ = version
            dlb.version_info = version_info

    def test_help_includes_documentation_url_for_development_version(self):
        version = dlb.__version__
        version_info = dlb.version_info

        try:
            dlb.__version__ = '1.2.3.dev1+a747'
            dlb.version_info = (1, 2, 3)
            sys.argv = [sys.argv[0]] + ['--help']
            r = dlb_launcher.main()
            self.assertEqual(0, r)
            regex = r'.*\nFull documentation at: <{}.*>.\n'.format(re.escape(self.documentation_url))
            self.assertRegex(sys.stdout.getvalue(), regex)
        finally:
            dlb.__version__ = version
            dlb.version_info = version_info

    def test_help_ignores_invalid_version(self):
        version = dlb.__version__
        version_info = dlb.version_info

        try:
            del dlb.version_info
            sys.argv = [sys.argv[0]] + ['--help']
            r = dlb_launcher.main()
            self.assertEqual(0, r)
        finally:
            dlb.__version__ = version
            dlb.version_info = version_info


class UsageTest(testenv.CommandlineToolTestCase,
                testenv.TemporaryWorkingDirectoryTestCase):

    def test_outputs_usage_without_parameters(self):
        r = dlb_launcher.main()
        self.assertEqual(2, r)
        regex = r'usage: .* {}\n'.format(re.escape('[ --help ] [ <script-name> [ <script-parameter> ... ] ]'))
        self.assertRegex(sys.stderr.getvalue(), regex)


class ScriptTest(testenv.CommandlineToolTestCase,
                 testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_empty_scriptname(self):
        sys.stderr = io.StringIO()
        script_name = ''
        sys.argv = [sys.argv[0], script_name]
        r = dlb_launcher.main()
        self.assertEqual(1, r)
        self.assertEqual(f'error: not a valid script name: {script_name!r}\n', sys.stderr.getvalue())

    def test_fails_for_scriptname_that_starts_with_minus(self):
        for script_name in ['', '-build.py']:
            sys.stderr = io.StringIO()
            sys.argv = [sys.argv[0], script_name]
            r = dlb_launcher.main()
            self.assertEqual(1, r)
            self.assertEqual(f'error: not a valid script name: {script_name!r}\n', sys.stderr.getvalue())

    def test_fails_for_absolute_path(self):
        sys.stderr = io.StringIO()
        script_name = os.path.abspath('build.py')
        sys.argv = [sys.argv[0], script_name]
        r = dlb_launcher.main()
        self.assertEqual(1, r)
        self.assertEqual(f'error: not a valid script name (since absolute): {script_name!r}\n', sys.stderr.getvalue())

    def test_fails_for_path_with_dotdot(self):  # except at end
        invalid_script_names = [
            os.path.join('..', 'build'),
            os.path.join('build', '..', '..', 'build')
        ]
        for script_name in invalid_script_names:
            sys.stderr = io.StringIO()
            sys.argv = [sys.argv[0], script_name]
            r = dlb_launcher.main()
            self.assertEqual(1, r)
            self.assertEqual(f"error: not a valid script name (since upwards path): {script_name + '.py'!r}\n",
                             sys.stderr.getvalue())

    def test_fails_for_nonexistent(self):
        script_name = 'build'
        sys.argv = [sys.argv[0], script_name]
        r = dlb_launcher.main()
        self.assertEqual(1, r)
        self.assertEqual(f"error: not an existing script: {script_name + '.py'!r}\n", sys.stderr.getvalue())

    def test_normalizes_nonupwards_path(self):
        script_name = os.path.join('build', '..', 'all', '.', 'build')
        normalized_script_name = os.path.join('all', 'build.py')
        os.mkdir('all')
        open(normalized_script_name, 'w').close()
        sys.stderr = io.StringIO()
        sys.argv = [sys.argv[0], script_name]
        r = dlb_launcher.main()
        self.assertEqual(0, r)

    def test_add_py_if_not_present(self):
        sys.stderr = io.StringIO()
        script_name = 'build'
        sys.argv = [sys.argv[0], script_name]
        open('build.py', 'w').close()
        r = dlb_launcher.main()
        self.assertEqual(0, r)

    def test_accepts_dot_at_end(self):
        sys.stderr = io.StringIO()
        script_name = '.'
        sys.argv = [sys.argv[0], script_name]
        open('..py', 'w').close()
        r = dlb_launcher.main()
        self.assertEqual(0, r)

    def test_accepts__dotdot_at_end(self):
        sys.stderr = io.StringIO()
        script_name = '..'
        sys.argv = [sys.argv[0], script_name]
        open('...py', 'w').close()
        r = dlb_launcher.main()
        self.assertEqual(0, r)

    def test_fails_for_directory(self):
        os.mkdir('build.py')
        script_name = 'build'
        sys.argv = [sys.argv[0], script_name]
        r = dlb_launcher.main()
        self.assertEqual(1, r)
        self.assertEqual(f"error: not an existing script: {script_name + '.py'!r}\n", sys.stderr.getvalue())

    def test_forwards_arguments(self):
        with open('build.py', 'x') as f:
            f.write(
                "import sys\n"
                "print(repr(sys.argv[1:]))\n"
            )

        sys.argv = [sys.argv[0]] + ['build', 'a\nb', 'c ']
        r = dlb_launcher.main()
        self.assertEqual(0, r)
        self.assertEqual("['a\\nb', 'c ']\n", sys.stdout.getvalue())

    def test_script_identity(self):
        script_path = os.path.abspath('build.py')
        with open(script_path, 'x') as f:
            f.write(
                "import sys\n"
                "print(repr(sys.argv[0]))\n"
                "print(repr(__file__))\n"
                "print(repr(__name__))\n"
            )

        sys.argv = [sys.argv[0]] + ['build']
        r = dlb_launcher.main()
        self.assertEqual(0, r)
        msg = f"{script_path!r}\n{script_path!r}\n{'__main__'!r}\n"
        self.assertEqual(msg, sys.stdout.getvalue())


class HistoryTest(testenv.CommandlineToolTestCase,
                  testenv.TemporaryWorkingDirectoryTestCase):

    def test_includes_script_name_and_script_parameters(self):
        open('build.py', 'xb').close()

        sys.argv = [sys.argv[0]] + ['build', 'a\nb', 'c ']
        r = dlb_launcher.main()
        self.assertEqual(0, r)

        with open(os.path.join('.dlbroot', f'last.{os.name}'), 'rb') as f:
            history = f.read().decode()
        self.assertEqual("['build.py', 'a\\nb', 'c ']", history)

    def test_uses_last_with_parameters(self):
        with open(os.path.join('.dlbroot', f'last.{os.name}'), 'wb') as f:
            f.write("['build.py', 'a\\nb', 'c ']".encode())

        with open('build.py', 'x') as f:
            f.write(
                "import sys\n"
                "print(repr(sys.argv[1:]))\n"
            )

        r = dlb_launcher.main()
        self.assertEqual(0, r)
        self.assertEqual("['a\\nb', 'c ']\n", sys.stdout.getvalue())
        self.assertEqual("using arguments of last successful run: 'build.py', 'a\\nb', 'c '\n", sys.stderr.getvalue())

        with open(os.path.join('.dlbroot', f'last.{os.name}'), 'rb') as f:
            history = f.read().decode()
        self.assertEqual("['build.py', 'a\\nb', 'c ']", history)

    def test_fails_for_invalid_history(self):
        invalid_history_contents = [
            "1",
            "[]",
            "['1', 2]",
            "['-']",
            "['-x']",
            '[{!r}]'.format(f'{os.getcwd()}{os.path.sep}build.py'),
            '[{!r}]'.format(f'{os.path.sep}build.py'),
            '[{!r}]'.format(f'..{os.path.sep}build.py')
        ]

        history_file_path = os.path.abspath(os.path.join('.dlbroot', f'last.{os.name}'))

        for history_content in invalid_history_contents:
            with open(history_file_path, 'wb') as f:
                f.write(history_content.encode())
            sys.stderr = io.StringIO()
            r = dlb_launcher.main()
            self.assertEqual(1, r)
            self.assertEqual(f'error: invalid dlb history file (remove it manually): {history_file_path!r}\n',
                             sys.stderr.getvalue())


class InaccessibleHistoryTest(testenv.TemporaryDirectoryWithChmodTestCase,
                              testenv.TemporaryWorkingDirectoryTestCase):

    def test_outputs_usage_if_inaccessible_before(self):
        history_file_path = os.path.abspath(os.path.join('.dlbroot', f'last.{os.name}'))
        open(history_file_path, 'wb').close()
        stderr = sys.stderr
        try:
            os.chmod(history_file_path, 0o000)
            sys.stderr = io.StringIO()
            r = dlb_launcher.main()
            self.assertEqual(2, r)
            self.assertRegex(sys.stderr.getvalue(), r'usage: .*\n')
        finally:
            sys.stderr = stderr
            os.chmod(history_file_path, 0o666)

    def test_ignores_inaccessible_after(self):
        history_file_path = os.path.abspath(os.path.join('.dlbroot', f'last.{os.name}'))
        open(history_file_path, 'wb').close()
        open('build.py', 'xb').close()
        stderr = sys.stderr
        try:
            os.chmod(history_file_path, 0o000)
            sys.stderr = io.StringIO()
            sys.argv = [sys.argv[0]] + ['build']
            r = dlb_launcher.main()
            self.assertEqual(0, r)
            self.assertEqual('', sys.stderr.getvalue())
        finally:
            sys.stderr = stderr
            os.chmod(history_file_path, 0o666)


class ModuleSearchPathTest(testenv.CommandlineToolTestCase,
                           testenv.TemporaryWorkingDirectoryTestCase):

    def test_adds_zip_files_to_module_search_path(self):
        u_path = os.path.join('.dlbroot', 'u')
        os.mkdir(u_path)
        open(os.path.join(u_path, 'x.zip'), 'xb').close()
        open(os.path.join(u_path, 'y.zip'), 'xb').close()
        open(os.path.join(u_path, '.zip'), 'xb').close()
        os.mkdir(os.path.join(u_path, 'd.zip'))

        with open('build.py', 'x') as f:
            f.write(
                "import sys\n"
                "import os\n"
                "assert all(os.path.isabs(p) for p in sys.path)\n"
                "cwd = os.getcwd()\n"
                "local_paths = [os.path.relpath(p, cwd) for p in sys.path if p.startswith(cwd)]\n"
                "print(repr(local_paths))\n"
            )

        sys.argv = [sys.argv[0]] + ['build']
        r = dlb_launcher.main()
        self.assertEqual(0, r)

        rel_module_search_paths = ['.', os.path.join(u_path, 'x.zip'), os.path.join(u_path, 'y.zip')]
        self.assertEqual(repr(rel_module_search_paths) + '\n', sys.stdout.getvalue())
        self.assertEqual("adding 2 zip file(s) to module search path\n", sys.stderr.getvalue())

    def test_directory_of_script_is_first(self):
        os.mkdir('build')

        script_path = os.path.abspath(os.path.join('build', 'show.py'))
        with open(script_path, 'x') as f:
            f.write(
                "import sys\n"
                "print(repr(sys.path[0]))\n"
            )

        sys.argv = [sys.argv[0]] + [os.path.join('build', 'show')]
        r = dlb_launcher.main()
        self.assertEqual(0, r)
        self.assertEqual(repr(os.path.dirname(script_path)) + '\n', sys.stdout.getvalue())
