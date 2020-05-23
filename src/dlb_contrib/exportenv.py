# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Export environment variables to an UTF-8 encoded JSON file in the current directory.
To be used by batch files and shell scripts (see dlb_contrib.msbatch)."""

# JSON: <https://tools.ietf.org/html/rfc8259>
#
# Usage example:
#
#   # e.g. in a batch file
#   python3 -m dlb_contrib.exportenv
#
#   # 'env.json' now looks like this:
#   # {"XY": "a line\nand another one"}

__all__ = ['export', 'read_exported']

import sys
import os
import json
from typing import Dict

assert sys.version_info >= (3, 7)

FILE_NAME = 'env.json'


def export(file_path: os.fspath = FILE_NAME):
    # Export all environment variables to JSON file *file_path*.
    #
    # Fails if *file_path* is the path of an existing filesystem object.
    # Strings are backslash escaped.

    environment = {k: v for k, v in os.environ.items()}
    with open(file_path, 'x', encoding='utf-8') as f:
        json.dump(environment, f, ensure_ascii=False, check_circular=False)


def read_exported(file_path: os.fspath = FILE_NAME) -> Dict[str, str]:
    # Read environment variables exported by export() from JSON file *file_path*.

    with open(file_path, 'r', encoding='utf-8') as f:
        environment = json.load(f)
    if not isinstance(environment, dict) or \
            not all(isinstance(k, str) and isinstance(v, str) for k, v, in environment.items()):
        raise TypeError('not a dictionary of str')
    return environment


if __name__ == '__main__':
    export()
