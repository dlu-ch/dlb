# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2022 Daniel Lutz <dlu-ch@users.noreply.github.com>

import unittest

try:
    test_report_file = open(3, 'w', buffering=1)
except OSError:  # e.g. because file descriptor 3 not opened by parent process
    test_report_file = None  # results in report output to sys.stderr

runner = unittest.TextTestRunner(stream=test_report_file, verbosity=2)
unittest.main(module=None, testRunner=runner)
