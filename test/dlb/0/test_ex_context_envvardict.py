# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.ex
import re
import os
import unittest


class ThisIsAUnitTest(unittest.TestCase):
    pass


class ImportFromOuterTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_import_fails_if_argument_type_is_incorrect(self):
        with dlb.ex.Context() as c:
            regex = r"'.+' must be a str"
            with self.assertRaisesRegex(TypeError, regex):
                # noinspection PyTypeChecker
                c.env.import_from_outer(None, pattern=r'X.*Z', example='XZ')
            with self.assertRaisesRegex(TypeError, regex):
                # noinspection PyTypeChecker
                c.env.import_from_outer('A_B_C', pattern=r'X.*Z', example=None)
            with self.assertRaisesRegex(TypeError, regex):
                # noinspection PyTypeChecker
                c.env.import_from_outer('A_B_C', pattern=r'X.*Z', example=b'XZ')

            regex = re.escape("'name' must not be empty")
            with self.assertRaisesRegex(ValueError, regex):
                c.env.import_from_outer('', pattern=r'X.*Z', example='XZ')

            regex = re.escape(r"'pattern' must be regular expression (compiled or str)")
            with self.assertRaisesRegex(TypeError, regex):
                # noinspection PyTypeChecker
                c.env.import_from_outer('A_B_C', pattern=None, example='XZ')
            with self.assertRaisesRegex(TypeError, regex):
                # noinspection PyTypeChecker
                c.env.import_from_outer('A_B_C', pattern=b'', example='XZ')

    def test_import_fails_if_validation_pattern_does_not_match_example(self):
        with dlb.ex.Context() as c:
            regex = r"\A'example' is not matched by 'pattern': '.*'\Z"
            with self.assertRaisesRegex(ValueError, regex):
                c.env.import_from_outer('A_B_C', pattern=r'X.*Z', example='')
            with self.assertRaisesRegex(ValueError, regex):
                c.env.import_from_outer('A_B_C', pattern=re.compile(r'X.*Z'), example='')

    def test_is_imported_after_import(self):
        with dlb.ex.Context():
            self.assertFalse(dlb.ex.Context.active.env.is_imported('W'))
            dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern='.*', example='')
            self.assertTrue(dlb.ex.Context.active.env.is_imported('A_B_C'))
            self.assertFalse('A_B_C' in dlb.ex.Context.active.env)

            with dlb.ex.Context():
                self.assertFalse(dlb.ex.Context.active.env.is_imported('W'))
                dlb.ex.Context.active.env.import_from_outer('UV', pattern='.*', example='')
                self.assertTrue(dlb.ex.Context.active.env.is_imported('A_B_C'))

                with dlb.ex.Context():
                    self.assertFalse(dlb.ex.Context.active.env.is_imported('W'))
                    self.assertTrue(dlb.ex.Context.active.env.is_imported('A_B_C'))
                    self.assertTrue(dlb.ex.Context.active.env.is_imported('UV'))

                    with dlb.ex.Context():
                        self.assertFalse(dlb.ex.Context.active.env.is_imported('W'))
                        self.assertTrue(dlb.ex.Context.active.env.is_imported('A_B_C'))
                        self.assertTrue(dlb.ex.Context.active.env.is_imported('UV'))

    def test_validation_pattern_of_outer_applies_when_imported(self):
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'.*', example='')
            dlb.ex.Context.active.env['A_B_C'] = 'XYZ'

            with dlb.ex.Context():
                regex = r"current value is not matched by 'pattern': 'XYZ'"
                with self.assertRaisesRegex(ValueError, regex):
                    dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'.y.', example='XyZ')

                dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')

                with dlb.ex.Context():
                    with dlb.ex.Context():
                        regex = r"current value is not matched by 'pattern': 'XYZ'"
                        with self.assertRaisesRegex(ValueError, regex):
                            dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'.y.', example='XyZ')
                        dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'.Y.', example='aYc')

    def test_validation_pattern_of_outer_applies_when_assigned(self):
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')
            with dlb.ex.Context():
                with dlb.ex.Context():
                    dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'.y.', example='XyZ')
                    dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'.Y.', example='XYZ')

                    with self.assertRaises(ValueError) as cm:
                        dlb.ex.Context.active.env['A_B_C'] = 'xYz'
                    msg = (
                        "'value' is not matched by associated validation pattern: 'xYz'\n"
                        "  | validation pattern in question is 'X.*Z'"
                    )
                    self.assertEqual(str(cm.exception), msg)

    def test_root_context_does_not_import_from_os_environ(self):
        orig_a_b_c = os.environ.get('A_B_C')
        try:
            os.environ['A_B_C'] = 'XYZ'
            with dlb.ex.Context():
                self.assertFalse('A_B_C' in dlb.ex.Context.active.env)
                dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')
                self.assertFalse('A_B_C' in dlb.ex.Context.active.env)
                with self.assertRaises(KeyError) as cm:
                    dlb.ex.Context.active.env['A_B_C']
        finally:
            os.environ.pop('A_B_C', None)
            if orig_a_b_c is not None:
                os.environ['A_B_C'] = orig_a_b_c
        msg = (
            "not a defined environment variable in the context: 'A_B_C'\n"
            "  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...] = ...'"
        )
        self.assertEqual(str(cm.exception), repr(msg))

    def test_imported_is_initially_undefined(self):
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')
            self.assertIsNone(dlb.ex.Context.active.env.get('A_B_C'))
            self.assertFalse('A_B_C' in dlb.ex.Context.active.env)
            self.assertTrue('A_B_C' not in dlb.ex.Context.active.env)
            self.assertEqual(0, len(dlb.ex.Context.active.env))
            self.assertEqual(0, len([e for e in dlb.ex.Context.active.env]))
            self.assertEqual(0, len(dlb.ex.Context.active.env.items()))

    def test_imported_can_be_assigned_and_deleted(self):
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')
            self.assertFalse('A_B_C' in dlb.ex.Context.active.env)

            dlb.ex.Context.active.env['A_B_C'] = 'XYZ'
            self.assertEqual(dlb.ex.Context.active.env['A_B_C'], 'XYZ')
            
            with dlb.ex.Context():
                self.assertEqual(dlb.ex.Context.active.env['A_B_C'], 'XYZ')
                del dlb.ex.Context.active.env['A_B_C']
                self.assertEqual(dlb.ex.Context.active.env.get('A_B_C'), None)
                with self.assertRaises(KeyError) as cm:
                    dlb.ex.Context.active.env['A_B_C']
                msg = (
                    "not a defined environment variable in the context: 'A_B_C'\n"
                    "  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...] = ...'"
                )
                self.assertEqual(str(cm.exception), repr(msg))

                with dlb.ex.Context():
                    dlb.ex.Context.active.env['A_B_C'] = 'XYYYZ'
                    self.assertEqual(dlb.ex.Context.active.env['A_B_C'], 'XYYYZ')

                self.assertEqual(dlb.ex.Context.active.env.get('A_B_C'), None)

            self.assertEqual(dlb.ex.Context.active.env['A_B_C'], 'XYZ')
            del dlb.ex.Context.active.env['A_B_C']

    def test_assigned_of_nonstr_to_imported_fails(self):
        msg = "'value' must be a str"

        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('ABC', pattern=r'.*', example='')

            with self.assertRaises(TypeError) as cm:
                # noinspection PyTypeChecker
                dlb.ex.Context.active.env['ABC'] = 1
            self.assertEqual(msg, str(cm.exception))

            with self.assertRaises(TypeError) as cm:
                # noinspection PyTypeChecker
                dlb.ex.Context.active.env['ABC'] = None
            self.assertEqual(msg, str(cm.exception))

    def test_import_fails_on_inactive_context(self):
        with dlb.ex.Context() as c0:
            env0 = c0.env
            with dlb.ex.Context() as c1:
                env1 = c1.env
                with dlb.ex.Context():
                    regex = (
                        r"(?m)\A"
                        r"'env' of an inactive context must not be modified\n"
                        r"  \| use 'dlb\.ex\.Context\.active\.env' to get 'env' of the active context\Z"
                    )
                    with self.assertRaisesRegex(dlb.ex._error.ContextModificationError, regex):
                        env0.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')
                    with self.assertRaisesRegex(dlb.ex._error.ContextModificationError, regex):
                        env1.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')


# noinspection PyUnresolvedReferences
class AccessTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_empty_dict_access(self):
        with dlb.ex.Context() as c:
            self.assertEqual(len(c.env), 0)
            self.assertFalse('x' in c.env)
            self.assertTrue('x' not in c.env)
            self.assertEqual([k for k in c.env], [])
            self.assertEqual({k: v for k, v in c.env.items()}, dict())

    def test_env_returns_env_of_active_context(self):
        c0 = dlb.ex.Context()
        with self.assertRaises(dlb.ex._error.NotRunningError):
            c0.env
        with c0:
            env0 = c0.env
            self.assertIs(c0.env, env0)
            with dlb.ex.Context() as c1:
                env1 = c1.env
                self.assertIs(c0.env, env0)
                self.assertIs(c1.env, env1)
                self.assertIs(dlb.ex.Context.active.env, env1)
                with dlb.ex.Context() as c2:
                    env2 = c2.env
                    self.assertIs(c0.env, env0)
                    self.assertIs(c1.env, env1)
                    self.assertIs(c2.env, env2)
                    self.assertIs(dlb.ex.Context.active.env, env2)
        with self.assertRaises(dlb.ex._error.NotRunningError):
            c0.env

    def test_deletion_fails_if_undefined(self):
        with dlb.ex.Context():
            with self.assertRaises(KeyError) as cm:
                del dlb.ex.Context.active.env['A_B_C']
            msg = "not a defined environment variable in the context: 'A_B_C'"
            self.assertEqual(str(cm.exception), repr(msg))

    def test_assignment_fail_if_not_imported(self):
        with dlb.ex.Context():
            regex = (
                r"(?m)\A"
                r"environment variable not imported into context: 'A_B_C'\n"
                r"  \| use 'dlb\.ex\.Context\.active\.env.import_from_outer\(\)' first\Z"
            )
            with self.assertRaisesRegex(AttributeError, regex):
                dlb.ex.Context.active.env['A_B_C'] = 'XyZ'
            with dlb.ex.Context():
                with dlb.ex.Context():
                    with self.assertRaisesRegex(AttributeError, regex):
                        dlb.ex.Context.active.env['A_B_C'] = 'XyZ'

    def test_assignment_fails_on_inactive_context(self):
        with dlb.ex.Context() as c0:
            env0 = c0.env
            dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')
            with dlb.ex.Context() as c1:
                env1 = c1.env
                with dlb.ex.Context():
                    regex = (
                        r"(?m)\A"
                        r"'env' of an inactive context must not be modified\n"
                        r"  \| use 'dlb\.ex\.Context\.active\.env' to get 'env' of the active context\Z"
                    )
                    with self.assertRaisesRegex(dlb.ex._error.ContextModificationError, regex):
                        env0['A_B_C'] = 'XYYZ'
                    with self.assertRaisesRegex(dlb.ex._error.ContextModificationError, regex):
                        env1['A_B_C'] = 'XYYZ'

    def test_deletion_fails_on_inactive_context(self):
        with dlb.ex.Context() as c0:
            env0 = c0.env
            dlb.ex.Context.active.env.import_from_outer('A_B_C', pattern=r'X.*Z', example='XZ')
            with dlb.ex.Context() as c1:
                env1 = c1.env
                with dlb.ex.Context():
                    regex = (
                        r"(?m)\A"
                        r"'env' of an inactive context must not be modified\n"
                        r"  \| use 'dlb\.ex\.Context\.active\.env' to get 'env' of the active context\Z"
                    )
                    with self.assertRaisesRegex(dlb.ex._error.ContextModificationError, regex):
                        del env0['A_B_C']
                    with self.assertRaisesRegex(dlb.ex._error.ContextModificationError, regex):
                        del env1['A_B_C']


class UsageTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_example(self):
        orig_lang = os.environ.get('LANG')

        try:
            os.environ['LANG'] = 'en_UK'

            with dlb.ex.Context():

                # "import" the environment variable 'LANG' into the context
                dlb.ex.Context.active.env.import_from_outer('LANG', pattern=r'[a-z]{2}_[A-Z]{2}', example='sv_SE')
                dlb.ex.Context.active.env['LANG'] = os.environ['LANG']

                # now the environment variable is either undefined or matches the regular expression given
                # (in this context and all future inner contexts)

                _ = dlb.ex.Context.active.env['LANG']  # value satisfies the validation pattern(s) or KeyError is raised

                dlb.ex.Context.active.env['LANG'] = 'de_AT'

                with dlb.ex.Context():
                    # further restrict the value and make sure it is defined
                    dlb.ex.Context.active.env.import_from_outer('LANG', pattern='(?P<language>de).*', example='de_CH')

                    self.assertEqual(dlb.ex.Context.active.env['LANG'], 'de_AT')
                    del dlb.ex.Context.active.env['LANG']

                    dlb.ex.Context.active.env['LANG'] = 'de_CH'
                    with self.assertRaises(ValueError):
                        dlb.ex.Context.active.env['LANG'] = 'fr_FR'  # would raise ValueError

                self.assertEqual(dlb.ex.Context.active.env['LANG'], 'de_AT')
                del dlb.ex.Context.active.env['LANG']  # undefine 'LANG'
                self.assertNotIn('LANG', dlb.ex.Context.active.env)
                dlb.ex.Context.active.env['LANG'] = 'fr_FR'  # ok

        finally:
            os.environ.pop('LANG', None)
            if orig_lang is not None:
                os.environ['LANG'] = orig_lang

    def test_has_repr(self):
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('LANG', pattern=r'.*', example='')
            dlb.ex.Context.active.env.import_from_outer('ABC', pattern=r'.*', example='')
            dlb.ex.Context.active.env['LANG'] = 'fr_FR'
            dlb.ex.Context.active.env['ABC'] = ''
            s = repr(dlb.ex.Context.active.env)
            self.assertEqual("EnvVarDict({'ABC': '', 'LANG': 'fr_FR'})", s)
