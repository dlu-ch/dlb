# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Launcher for a dlb script
This is an implementation detail - do not import it unless you know what you are doing."""

# Note:
#  - This is not significantly slower than a Bash script on GNU/Linux
#  - Python starts much faster than PowerShell even on Windows.

__all__ = ['main']

import sys
import os.path


def chdir_to_workingtree_root():
    while not os.path.isdir('.dlbroot'):
        cwd = os.getcwd()
        os.chdir('..')
        if cwd == os.getcwd():
            raise Exception("current working directory not in a dlb working tree (no '.dlbroot' found)")


def complete_module_search_path(dlbroot_path, script_abs_path):
    ext = '.zip'
    zip_files = []
    try:
        with os.scandir(os.path.join(dlbroot_path, 'u')) as it:
            zip_files = [e.path for e in it if e.is_file() and e.name.endswith(ext) and e.name != ext]
    except FileNotFoundError:
        pass
    sys.path = [os.path.abspath(p) for p in sys.path]
    if zip_files:
        print(f'adding {len(zip_files)} zip file(s) to module search path', file=sys.stderr)
        sys.path = zip_files + sys.path
    sys.path.insert(0, os.path.dirname(script_abs_path))


def complete_command_line(history_file_path, arguments):
    if arguments:
        script_name = arguments[0]
        if script_name and not script_name.endswith('.py'):
            script_name += '.py'
        return script_name, arguments[1:]

    last_arguments = None
    try:
        with open(history_file_path, 'rb') as f:
            last_arguments = f.read()
    except OSError:
        pass

    if last_arguments is None:
        return None, []

    import ast
    try:
        # ast.literal_eval():
        #   "It is possible to crash the Python interpreter with a sufficiently large/complex string due to stack depth
        #   limitations in Python’s AST compiler."
        last_arguments = ast.literal_eval(last_arguments.decode())
        if not (isinstance(last_arguments, list) and all(isinstance(a, str) for a in last_arguments)):
            raise TypeError
        if not last_arguments:
            raise ValueError
    except (SyntaxError, TypeError, ValueError, UnicodeDecodeError):
        raise Exception(f'invalid dlb history file (remove it manually): {history_file_path!r}')
    arguments_str = ', '.join(repr(a) for a in last_arguments)
    print(f'using arguments of last successful run: {arguments_str}', file=sys.stderr)
    return last_arguments[0], last_arguments[1:]


def find_script(script_name):
    if not script_name or script_name[0] == '-' or \
            os.path.isabs(script_name) or os.path.normpath(script_name) != script_name:
        raise Exception(f'not a script name: {script_name!r}')

    script_abs_path = os.path.abspath(script_name)
    if not os.path.isfile(script_abs_path):
        raise Exception(f'not an existing script: {script_name!r}')

    module_name = '__main__'

    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, script_abs_path)
    module = importlib.util.module_from_spec(spec)

    return script_abs_path, spec, module, module_name


def get_help():
    # 80 characters xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    help_msg = \
        """
        Run a dlb script in the root of the working tree that contains the current
        working directory.
    
        When called with '--help' as the first parameter, displays this help and exits.
    
        When called with a least one parameter and the first parameter is not '--help',
        the first parameter must be a dlb script as a normalized, non-upwards path
        relative to the root of the working tree that does not start with '-'. '.py' is
        appended if it does not end with '.py'. All other parameters are forwarded to
        the dlb script.
    
        When called without a parameter, the parameters from the last successful call of
        this script with the same 'os.name' are used.
    
        Each regular file or symbolic link to a regular file in the directory
        '.dlbroot/u/' of the working tree whose name ends in '.zip' is added to the list
        of module search paths of the Python interpreter.
    
        Exit status:
    
           0  if called with '--help'
           1  if the specified dlb script could not be executed
           2  if no command-line arguments were given and the command-line arguments
              of the last successful call are not available
           e  otherwise, where e is the exit status of the specified dlb script
              (0 if it finished successfully)
    
        Examples:
    
           dlb build/all         # executes the dlb script 'build/all.py' in the
                                 # working tree's root
           dlb                   # same as dlb build/all if the previous call
                                 # was successful
           PYTHONVERBOSE=1 dlb   # when called from a POSIX-compliant shell
           dlb --help
        """
    import textwrap
    help_msg = textwrap.dedent(help_msg).strip()

    try:
        import dlb
        doc_url = 'https://dlb.readthedocs.io/'
        if len(dlb.version_info) == 3 and '.dev' not in dlb.__version__:
            released_version = '.'.join(str(c) for c in dlb.version_info)
            doc_url += f"en/v{released_version}/"
        help_msg += f"\n\ndlb version: {dlb.__version__}.\nFull documentation at: <{doc_url}>."
    except (ImportError, AttributeError):
        pass

    return help_msg


def main():
    if sys.argv[1:2] == ['--help']:
        print(get_help())
        return 0

    try:
        chdir_to_workingtree_root()
        dlbroot_path = os.path.abspath('.dlbroot')

        # history contains paths; representation of paths depends only on 'os.name'
        history_file_path = os.path.join(dlbroot_path, f'last.{os.name}')

        script_name, script_arguments = complete_command_line(history_file_path, sys.argv[1:])
        if script_name is None:
            executable_name = os.path.basename(sys.argv[0])
            if not all(' ' < c < chr(0x7F) for c in executable_name):
                executable_name = repr(executable_name)
            print(f'usage: {executable_name} [ --help ] [ <script-name> [ <script-parameter> ... ] ]', file=sys.stderr)
            return 2
        script_abs_path, spec, module, module_name = find_script(script_name)
        complete_module_search_path(dlbroot_path, script_abs_path)
    except Exception as e:
        print(f'error: {e}', file=sys.stderr)
        return 1

    sys.argv = [script_abs_path] + script_arguments
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # may change the working directory of the process and sys.argv

    # noinspection PyBroadException
    try:
        with open(history_file_path, 'wb') as f:
            f.write(repr([script_name] + script_arguments).encode())
    except Exception:
        pass

    return 0
