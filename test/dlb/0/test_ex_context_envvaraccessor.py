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


class NameTest(unittest.TestCase):

    def test_construction_fails_if_argument_type_is_incorrect(self):
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            dlb.ex.EnvVarAccessor(42)
        self.assertEqual("'name' must be a str", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            dlb.ex.EnvVarAccessor("")
        self.assertEqual("'name' must not be empty", str(cm.exception))

    def test_name_is_from_construction(self):
        accessor = dlb.ex.EnvVarAccessor("xy")
        self.assertEqual('xy', accessor.name)


class GetTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_if_not_running(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with self.assertRaises(dlb.ex.NotRunningError):
            accessor.get(default=42)

    def test_is_default_if_undeclared_by_default(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            self.assertEqual(42, accessor.get(default=42))

    def test_fails_if_undeclared_and_required(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            with self.assertRaises(AttributeError) as cm:
                accessor.get(default=42, require_definition=True)
        self.assertEqual("environment variable not declared in context: 'xy'\n"
                         "  | use 'dlb.ex.Context.active.env.declare()' first",
                         str(cm.exception))

    def test_is_default_if_declared_but_undefined(self):
        with dlb.ex.Context():
            accessor = dlb.ex.Context.active.env.declare('A_B_C', pattern=r'.+', example='x')
            self.assertEqual(42, accessor.get(default=42))


class IsDeclaredTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_if_not_running(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with self.assertRaises(dlb.ex.NotRunningError):
            accessor.is_declared()

    def test_false_if_undeclared(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            self.assertFalse(accessor.is_declared())
            with dlb.ex.Context():
                self.assertFalse(accessor.is_declared())

    def test_true_if_declared(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.*', example='')
            self.assertTrue(accessor.is_declared())
            with dlb.ex.Context():
                self.assertTrue(accessor.is_declared())


class IsDefinedTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_if_not_running(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with self.assertRaises(dlb.ex.NotRunningError):
            accessor.is_defined()

    def test_false_if_undeclared(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            self.assertFalse(accessor.is_defined())
            with dlb.ex.Context():
                self.assertFalse(accessor.is_defined())

    def test_true_if_declared_but_undefined(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.*', example='')
            self.assertFalse(accessor.is_defined())
            with dlb.ex.Context():
                self.assertFalse(accessor.is_defined())

    def test_true_if_defined(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.*', example='')
            self.assertFalse(accessor.is_defined())
            with dlb.ex.Context():
                dlb.ex.Context.active.env['xy'] = ''
                self.assertTrue(accessor.is_defined())


class SetTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_if_not_running(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with self.assertRaises(dlb.ex.NotRunningError):
            accessor.set('')

    def test_fails_if_undeclared(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        msg = (
            "environment variable not declared in context: 'xy'\n"
            "  | use 'dlb.ex.Context.active.env.declare()' first"
        )
        with dlb.ex.Context():
            with self.assertRaises(AttributeError) as cm:
                accessor.set('')
            self.assertEqual(msg, str(cm.exception))
            with self.assertRaises(AttributeError) as cm:
                accessor.set(None, required=False)
            self.assertEqual(msg, str(cm.exception))

    def test_fails_if_none_and_required(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            with self.assertRaises(ValueError) as cm:
                accessor.set(None)
        self.assertEqual("'value' other than None required", str(cm.exception))

    def test_fails_if_invalid(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.+', example=' ')
            with self.assertRaises(ValueError) as cm:
                accessor.set('')
        self.assertEqual("invalid value: ''\n"
                         "  | not matched by validation pattern '.+'", str(cm.exception))

    def test_defines_or_undefined_if_declared(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.+', example=' ')
            accessor.set(' ')
            self.assertTrue(accessor.is_defined())
            self.assertEqual(' ', accessor.get())
            with dlb.ex.Context():
                self.assertEqual(' ', accessor.get())
            accessor.set(None, required=False)
            self.assertFalse(accessor.is_defined())
            self.assertIsNone(accessor.get())

    def test_defines_value_in_active_context(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.*', example='')
            accessor.set('xy')
            with dlb.ex.Context():
                with dlb.ex.Context():
                    accessor.set('z')
                    self.assertEqual('z', dlb.ex.Context.active.env[accessor.name])
            self.assertEqual('xy', dlb.ex.Context.active.env[accessor.name])


class SetFromOuterTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_if_not_running(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with self.assertRaises(dlb.ex.NotRunningError):
            accessor.set_from_outer()

    def test_fails_if_no_outer(self):
        msg = 'active context has no outer context'
        accessor = dlb.ex.EnvVarAccessor('xy')

        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.*', example='')

            with self.assertRaises(ValueError) as cm:
                accessor.set_from_outer(required=False)
            self.assertEqual(msg, str(cm.exception))

            with self.assertRaises(ValueError) as cm:
                accessor.set_from_outer(required=True)
            self.assertEqual(msg, str(cm.exception))

    def test_defines_in_active_context(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.+', example=' ')
            accessor.set('xy')
            with dlb.ex.Context():
                with dlb.ex.Context():
                    dlb.ex.Context.active.env.declare('xy', pattern=r'.*', example='')
                    accessor.set('a')
                    self.assertEqual('a', accessor.get())
                    accessor.set_from_outer(required=True)
                    self.assertEqual('xy', accessor.get())
            self.assertEqual('xy', accessor.get())

    def test_does_not_define_if_undefined_in_outer_context(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.+', example=' ')
            with dlb.ex.Context():
                accessor.set_from_outer(required=False)
                self.assertFalse(accessor.is_defined())

                with self.assertRaises(KeyError) as cm:
                    accessor.set_from_outer(required=True)
                self.assertEqual(repr("required environment variable 'xy' not defined in outer context"),
                                 str(cm.exception))
            self.assertFalse(accessor.is_defined())

    def test_fails_if_defined_in_root_but_undefined_in_direct_outer_context(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.+', example=' ')
            accessor.set('xy')
            with dlb.ex.Context():
                accessor.set(None, required=False)
                self.assertFalse(accessor.is_defined())
                with dlb.ex.Context():
                    self.assertFalse(accessor.is_defined())
                    accessor.set('a')
                    with self.assertRaises(KeyError) as cm:
                        accessor.set_from_outer()
                    self.assertEqual(repr("required environment variable 'xy' not defined in outer context"),
                                     str(cm.exception))

    def test_fails_if_invalid_in_inner(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.declare('xy', pattern=r'.*', example='')
            accessor.set('xy')

            with dlb.ex.Context():
                with dlb.ex.Context():
                    with self.assertRaises(ValueError) as cm:
                        dlb.ex.Context.active.env.declare(accessor.name, pattern=r'.', example='x').set_from_outer()
                    self.assertEqual("invalid value: 'xy'\n  | not matched by validation pattern '.'",
                                     str(cm.exception))

            self.assertEqual('xy', dlb.ex.Context.active.env[accessor.name])


class SetFromOsTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_if_not_running(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with self.assertRaises(dlb.ex.NotRunningError):
            accessor.set_from_os(required=False)

    def test_fails_if_name_invalid(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            accessor.set_from_os(name=42)
        self.assertEqual("'name' must be None or a str", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            accessor.set_from_os(name='')
        self.assertEqual("'name' must not be empty", str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            accessor.set_from_os(default=42)
        self.assertEqual("'default' must be None or a str", str(cm.exception))

    def test_fails_if_expected_invalid(self):
        accessor = dlb.ex.EnvVarAccessor('xy')
        with self.assertRaises(TypeError) as cm:
            # noinspection PyTypeChecker
            accessor.set_from_os(expected=42)
        self.assertEqual("'expected' must be None or a str", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            accessor.set_from_os(expected='a\tb')
        self.assertEqual("'expected' must not contain ASCII control characters "
                         "except line separators, unlike '\\t'", str(cm.exception))

    def test_fails_if_invalid(self):
        orig_lang = os.environ.get('LANG')

        try:
            os.environ['LANG'] = 'bla'

            with dlb.ex.Context():
                dlb.ex.Context.active.env.declare('LANG', pattern=r'[a-z]{2}_[A-Z]{2}', example='fr_FR')
                accessor = dlb.ex.EnvVarAccessor('LANG')
                with self.assertRaises(ValueError) as cm:
                    accessor.set_from_os()
                self.assertEqual("invalid value of OS environment variable 'LANG': 'bla'\n"
                                 "  | not matched by validation pattern '[a-z]{2}_[A-Z]{2}'",
                                 str(cm.exception))
                with self.assertRaises(ValueError) as cm:
                    accessor.set_from_os(expected="expected language (ISO 639-1) and "
                                                  "territory (ISO 3166-1 alpha-2)")
                self.assertEqual("invalid value of OS environment variable 'LANG': 'bla'\n"
                                 "  | expected language (ISO 639-1) and territory (ISO 3166-1 alpha-2)",
                                 str(cm.exception))

                dlb.ex.Context.active.env.declare('UV', pattern=r'[a-z]{2}_[A-Z]{2}', example='fr_FR')
                accessor = dlb.ex.EnvVarAccessor('UV')
                with self.assertRaises(ValueError) as cm:
                    accessor.set_from_os(name='LANG')
                self.assertEqual("invalid value of OS environment variable 'LANG': 'bla'\n"
                                 "  | not matched by validation pattern '[a-z]{2}_[A-Z]{2}'",
                                 str(cm.exception))
                with self.assertRaises(ValueError) as cm:
                    accessor.set_from_os(name='LANG', expected="expected language (ISO 639-1) and "
                                                               "territory (ISO 3166-1 alpha-2)")
                self.assertEqual("invalid value of OS environment variable 'LANG': 'bla'\n"
                                 "  | expected language (ISO 639-1) and territory (ISO 3166-1 alpha-2)",
                                 str(cm.exception))
        finally:
            os.environ.pop('LANG', None)
            if orig_lang is not None:
                os.environ['LANG'] = orig_lang

    def test_fails_if_undeclared(self):
        orig_lang = os.environ.get('LANG')

        try:
            os.environ.pop('LANG', None)

            with dlb.ex.Context():
                accessor = dlb.ex.EnvVarAccessor('LANG')
                msg = (
                    "environment variable not declared in context: 'LANG'\n"
                    "  | use 'dlb.ex.Context.active.env.declare()' first"
                )
                with dlb.ex.Context():
                    with self.assertRaises(AttributeError) as cm:
                        accessor.set_from_os()
                    self.assertEqual(msg, str(cm.exception))
                    with self.assertRaises(AttributeError) as cm:
                        accessor.set_from_os(required=False)
                    self.assertEqual(msg, str(cm.exception))

            os.environ['LANG'] = 'bla'

            with dlb.ex.Context():
                accessor = dlb.ex.EnvVarAccessor('LANG')
                msg = (
                    "environment variable not declared in context: 'LANG'\n"
                    "  | use 'dlb.ex.Context.active.env.declare()' first"
                )
                with dlb.ex.Context():
                    with self.assertRaises(AttributeError) as cm:
                        accessor.set_from_os()
                    self.assertEqual(msg, str(cm.exception))
                    with self.assertRaises(AttributeError) as cm:
                        accessor.set_from_os(required=False)
                    self.assertEqual(msg, str(cm.exception))

        finally:
            os.environ.pop('LANG', None)
            if orig_lang is not None:
                os.environ['LANG'] = orig_lang

    def test_deletes_if_undefined_and_not_required(self):
        orig_lang = os.environ.get('LANG')

        try:
            os.environ.pop('LANG', None)

            with dlb.ex.Context():
                dlb.ex.Context.active.env.declare('LANG', pattern=r'.*', example='')
                accessor = dlb.ex.EnvVarAccessor('LANG')
                accessor.set('x')

                accessor.set_from_os(required=False)
                self.assertIsNone(accessor.get())

                dlb.ex.Context.active.env.declare('UV', pattern=r'.*', example='')
                accessor = dlb.ex.EnvVarAccessor('UV')
                accessor.set('x')

                accessor.set_from_os(name='LANG', required=False)
                self.assertIsNone(accessor.get())

        finally:
            os.environ.pop('LANG', None)
            if orig_lang is not None:
                os.environ['LANG'] = orig_lang

    def test_fails_if_undefined_and_required(self):
        orig_lang = os.environ.get('LANG')

        try:
            os.environ.pop('LANG', None)

            with dlb.ex.Context():
                dlb.ex.Context.active.env.declare('LANG', pattern=r'.*', example='')
                accessor = dlb.ex.EnvVarAccessor('LANG')
                with self.assertRaises(KeyError) as cm:
                    accessor.set_from_os(required=True)
                self.assertEqual(repr("OS environment variable 'LANG' not defined"), str(cm.exception))

                dlb.ex.Context.active.env.declare('UV', pattern=r'.*', example='')
                accessor = dlb.ex.EnvVarAccessor('UV')
                with self.assertRaises(KeyError) as cm:
                    accessor.set_from_os(name='LANG', required=True)
                self.assertEqual(repr("OS environment variable 'LANG' not defined"), str(cm.exception))

        finally:
            os.environ.pop('LANG', None)
            if orig_lang is not None:
                os.environ['LANG'] = orig_lang

    def test_exception_message_contains_normalised_expected_lines(self):
        orig_lang = os.environ.get('LANG')

        try:
            os.environ['LANG'] = 'bla'

            with dlb.ex.Context():
                dlb.ex.Context.active.env.declare('LANG', pattern=r'', example='')
                accessor = dlb.ex.EnvVarAccessor('LANG')
                with self.assertRaises(ValueError) as cm:
                    accessor.set_from_os(expected='xyz')
                self.assertEqual("invalid value of OS environment variable 'LANG': 'bla'\n"
                                 "  | xyz", str(cm.exception))

                with self.assertRaises(ValueError) as cm:
                    accessor.set_from_os(expected=(
                        'xyz  \r\n'
                        '\n'
                        '  \n'
                        '  uvz  '
                    ))
                self.assertEqual("invalid value of OS environment variable 'LANG': 'bla'\n"
                                 "  | xyz\n"
                                 "  |   uvz", str(cm.exception))

                with self.assertRaises(ValueError) as cm:
                    accessor.set_from_os(expected='')
                self.assertEqual("invalid value of OS environment variable 'LANG': 'bla'",
                                 str(cm.exception))

        finally:
            os.environ.pop('LANG', None)
            if orig_lang is not None:
                os.environ['LANG'] = orig_lang
