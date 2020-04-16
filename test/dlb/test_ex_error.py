# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.ex._error
import unittest


class ImportTest(unittest.TestCase):

    def test_all_from_tool_is_correct(self):
        self.assertEqual({
            'DefinitionAmbiguityError',
            'DependencyError',
            'ExecutionParameterError',
            'RedoError',
            'HelperExecutionError',
            'ContextNestingError',
            'NotRunningError',
            'ManagementTreeError',
            'NoWorkingTreeError',
            'WorkingTreeTimeError',
            'ContextModificationError',
            'WorkingTreePathError',
            'DatabaseError'
        }, set(dlb.ex._error.__all__))

        for n in dlb.ex._error.__all__:
            self.assertEqual('dlb.ex', dlb.ex._error.__dict__[n].__module__)
