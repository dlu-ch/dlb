import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import re
import os
import dlb.ex.context
import tools_for_test


class TechnicalInterfaceTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_empty_dict_access(self):
        os.mkdir('.dlbroot')

        with dlb.ex.Context() as c:
            self.assertEqual(len(c.env), 0)
            self.assertFalse('x' in c.env)
            self.assertTrue('x' not in c.env)
            self.assertEqual([k for k in c.env], [])
            self.assertEqual({k: v for k, v in c.env.items()}, dict())

    def test_import_fails_if_argument_type_is_incorrect(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c:
            regex = r"'.+' must be a str"
            with self.assertRaisesRegex(TypeError, regex):
                c.env.import_from_outer(None, r'X.*Z', example='XZ')
            with self.assertRaisesRegex(TypeError, regex):
                c.env.import_from_outer('A_B_C', r'X.*Z', example=None)
            with self.assertRaisesRegex(TypeError, regex):
                c.env.import_from_outer('A_B_C', r'X.*Z', example=b'XZ')

            regex = re.escape("'name' must not be empty")
            with self.assertRaisesRegex(ValueError, regex) as cm:
                c.env.import_from_outer('', r'X.*Z', example='XZ')

            regex = re.escape(r"'restriction' must be regular expression (compiled or str)")
            with self.assertRaisesRegex(TypeError, regex):
                c.env.import_from_outer('A_B_C', None, example='XZ')
            with self.assertRaisesRegex(TypeError, regex):
                c.env.import_from_outer('A_B_C', b'', example='XZ')

    def test_import_fails_if_example_is_invalid_with_respect_to_restriction(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c:
            regex = r"\A'example' is invalid with respect to 'restriction': '.*'\Z"
            with self.assertRaisesRegex(ValueError, regex):
                c.env.import_from_outer('A_B_C', r'X.*Z', example='')
            with self.assertRaisesRegex(ValueError, regex):
                c.env.import_from_outer('A_B_C', re.compile(r'X.*Z'), example='')

    def test_env_get_env_of_active_context(self):
        os.mkdir('.dlbroot')

        c0 = dlb.ex.Context()
        with self.assertRaises(dlb.ex.context.NotRunningError):
            c0.env
        with c0:
            env0 = c0.env
            self.assertIs(c0.env, env0)
            self.assertIs(dlb.ex.Context.env, env0)
            with dlb.ex.Context() as c1:
                env1 = c1.env
                self.assertIs(c0.env, env0)
                self.assertIs(c1.env, env1)
                self.assertIs(dlb.ex.Context.env, env0)
                self.assertIs(dlb.ex.Context.active.env, env1)
                with dlb.ex.Context() as c2:
                    env2 = c2.env
                    self.assertIs(c0.env, env0)
                    self.assertIs(c1.env, env1)
                    self.assertIs(c2.env, env2)
                    self.assertIs(dlb.ex.Context.env, env0)
                    self.assertIs(dlb.ex.Context.active.env, env2)
        with self.assertRaises(dlb.ex.context.NotRunningError):
            c0.env

    def test_after_import_envvar_is_imported(self):
        os.mkdir('.dlbroot')

        os.environ['A_B_C'] = 'XYZ'
        try:
            del os.environ['UV']
        except KeyError:
            pass
        try:
            del os.environ['W']
        except KeyError:
            pass

        with dlb.ex.Context():
            self.assertFalse(dlb.ex.Context.active.env.is_imported('W'))
            dlb.ex.Context.active.env.import_from_outer('A_B_C', restriction='.*', example='')
            self.assertTrue(dlb.ex.Context.active.env.is_imported('A_B_C'))

            with dlb.ex.Context():
                self.assertFalse(dlb.ex.Context.active.env.is_imported('W'))
                dlb.ex.Context.active.env.import_from_outer('UV', restriction='.*', example='')
                self.assertTrue(dlb.ex.Context.active.env.is_imported('A_B_C'))

                with dlb.ex.Context():
                    self.assertFalse(dlb.ex.Context.active.env.is_imported('W'))
                    self.assertTrue(dlb.ex.Context.active.env.is_imported('A_B_C'))
                    self.assertTrue(dlb.ex.Context.active.env.is_imported('UV'))

                    with dlb.ex.Context():
                        self.assertFalse(dlb.ex.Context.active.env.is_imported('W'))
                        self.assertTrue(dlb.ex.Context.active.env.is_imported('A_B_C'))
                        self.assertTrue(dlb.ex.Context.active.env.is_imported('UV'))

    def test_restriction_of_outer_applies_when_imported(self):
        os.mkdir('.dlbroot')

        os.environ['A_B_C'] = 'XYZ'
        with dlb.ex.Context():
            regex = r"imported value invalid with respect to 'restriction': 'XYZ'"
            with self.assertRaisesRegex(ValueError, regex):
                dlb.ex.Context.active.env.import_from_outer('A_B_C', r'.y.', example='XyZ')

            dlb.ex.Context.active.env.import_from_outer('A_B_C', r'X.*Z', example='XZ')

            with dlb.ex.Context():

                with dlb.ex.Context():

                    regex = r"current value invalid with respect to 'restriction': 'XYZ'"
                    with self.assertRaisesRegex(ValueError, regex):
                        dlb.ex.Context.active.env.import_from_outer('A_B_C', r'.y.', example='XyZ')

                    dlb.ex.Context.active.env.import_from_outer('A_B_C', r'.Y.', example='aYc')

    def test_restriction_of_outer_applies_when_assigned(self):
        os.mkdir('.dlbroot')

        os.environ.pop('A_B_C')
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('A_B_C', r'X.*Z', example='XZ')
            with dlb.ex.Context():
                with dlb.ex.Context():
                    dlb.ex.Context.active.env.import_from_outer('A_B_C', r'.y.', example='XyZ')
                    dlb.ex.Context.active.env.import_from_outer('A_B_C', r'.Y.', example='XYZ')

                    with self.assertRaises(ValueError) as cm:
                        dlb.ex.Context.active.env['A_B_C'] = 'xYz'
                    msg = "'value' invalid with respect to active or an outer context: 'xYz'"
                    self.assertEqual(str(cm.exception), msg)

    def test_imported_can_be_assigned_and_deleted(self):
        os.mkdir('.dlbroot')

        os.environ['A_B_C'] = 'XYZ'
        with dlb.ex.Context():
            dlb.ex.Context.active.env.import_from_outer('A_B_C', r'X.*Z', example='XZ')
            self.assertEqual(dlb.ex.Context.active.env['A_B_C'], 'XYZ')
            
            with dlb.ex.Context():
                self.assertEqual(dlb.ex.Context.active.env['A_B_C'], 'XYZ')
                del dlb.ex.Context.active.env['A_B_C']
                self.assertEqual(dlb.ex.Context.active.env.get('A_B_C'), None)
                with self.assertRaises(KeyError) as cm:
                    dlb.ex.Context.active.env['A_B_C']
                msg = (
                    "not a defined environment variable in the context: 'A_B_C'\n"
                    "  | use 'dlb.ex.Context.active.env.import_from_outer()' or 'dlb.ex.Context.active.env[...]' = ..."
                )
                self.assertEqual(str(cm.exception), repr(msg))

                with dlb.ex.Context():
                    dlb.ex.Context.active.env['A_B_C'] = 'XYYYZ'
                    self.assertEqual(dlb.ex.Context.active.env['A_B_C'], 'XYYYZ')

                self.assertEqual(dlb.ex.Context.active.env.get('A_B_C'), None)

            self.assertEqual(dlb.ex.Context.active.env['A_B_C'], 'XYZ')
            del dlb.ex.Context.active.env['A_B_C']

    def test_deletion_fails_if_undefined(self):
        os.mkdir('.dlbroot')

        os.environ['A_B_C'] = 'XYZ'
        with dlb.ex.Context():
            with self.assertRaises(KeyError) as cm:
                del dlb.ex.Context.active.env['A_B_C']
            msg = "not a defined environment variable in the context: 'A_B_C'"
            self.assertEqual(str(cm.exception), repr(msg))

    def test_assignment_fail_if_not_imported(self):
        os.mkdir('.dlbroot')

        os.environ['A_B_C'] = 'XYZ'
        with dlb.ex.Context():
            regex = (
                r"(?m)"
                r"\Aenvironment variable not imported into context: 'A_B_C'\n"
                r"  \| use 'dlb\.ex\.Context\.active\.env.import_from_outer\(\)' first\Z"
            )
            with self.assertRaisesRegex(AttributeError, regex):
                dlb.ex.Context.active.env['A_B_C'] = 'XyZ'
            with dlb.ex.Context():
                with dlb.ex.Context():
                    with self.assertRaisesRegex(AttributeError, regex):
                        dlb.ex.Context.active.env['A_B_C'] = 'XyZ'

    def test_import_fails_on_inactive_context(self):
        os.mkdir('.dlbroot')
        with dlb.ex.Context() as c0:
            env0 = c0.env
            with dlb.ex.Context() as c1:
                env1 = c1.env
                with dlb.ex.Context():
                    regex = (
                        r"(?m)"
                        r"\A'env' of an inactive context must not be modified\n"
                        r"  \| use 'dlb\.ex\.Context\.active\.env' to get 'env' of the active context\Z"
                    )
                    with self.assertRaisesRegex(dlb.ex.context.NonActiveContextAccessError, regex):
                        env0.import_from_outer('A_B_C', r'X.*Z', example='XZ')
                    with self.assertRaisesRegex(dlb.ex.context.NonActiveContextAccessError, regex):
                        env1.import_from_outer('A_B_C', r'X.*Z', example='XZ')

    def test_assignment_fails_on_inactive_context(self):
        os.mkdir('.dlbroot')

        os.environ['A_B_C'] = 'XYZ'
        with dlb.ex.Context() as c0:
            env0 = c0.env
            dlb.ex.Context.active.env.import_from_outer('A_B_C', r'X.*Z', example='XZ')
            with dlb.ex.Context() as c1:
                env1 = c1.env
                with dlb.ex.Context():
                    regex = (
                        r"(?m)"
                        r"\A'env' of an inactive context must not be modified\n"
                        r"  \| use 'dlb\.ex\.Context\.active\.env' to get 'env' of the active context\Z"
                    )
                    with self.assertRaisesRegex(dlb.ex.context.NonActiveContextAccessError, regex):
                        env0['A_B_C'] = 'XYYZ'
                    with self.assertRaisesRegex(dlb.ex.context.NonActiveContextAccessError, regex):
                        env1['A_B_C'] = 'XYYZ'

    def test_deletion_fails_on_inactive_context(self):
        os.mkdir('.dlbroot')

        os.environ['A_B_C'] = 'XYZ'
        with dlb.ex.Context() as c0:
            env0 = c0.env
            dlb.ex.Context.active.env.import_from_outer('A_B_C', r'X.*Z', example='XZ')
            with dlb.ex.Context() as c1:
                env1 = c1.env
                with dlb.ex.Context():
                    regex = (
                        r"(?m)"
                        r"\A'env' of an inactive context must not be modified\n"
                        r"  \| use 'dlb\.ex\.Context\.active\.env' to get 'env' of the active context\Z"
                    )
                    with self.assertRaisesRegex(dlb.ex.context.NonActiveContextAccessError, regex):
                        del env0['A_B_C']
                    with self.assertRaisesRegex(dlb.ex.context.NonActiveContextAccessError, regex):
                        del env1['A_B_C']

    def test_example(self):
        os.mkdir('.dlbroot')
        try:
            del os.environ['LANG']
        except KeyError:
            pass

        with dlb.ex.Context():  # takes a snapshot of os.environ

            # import the environment variable 'LANG' into the context
            dlb.ex.Context.active.env.import_from_outer('LANG', r'[a-z]{2}_[A-Z]{2}', example='sv_SE')

            # now the environment variable is either undefined or matches the regular expression given
            # (in this context and all future inner contexts)

            with self.assertRaises(KeyError):
                dlb.ex.Context.active.env['LANG']  # value in snapshot of os.environ matching the validator or KeyError

            dlb.ex.Context.active.env['LANG'] = 'de_AT'

            with dlb.ex.Context():
                # further restrict the value and make sure it is defined
                dlb.ex.Context.active.env.import_from_outer('LANG', '(?P<language>de).*', example='de_CH')

                self.assertEqual(dlb.ex.Context.active.env['LANG'], 'de_AT')
                del dlb.ex.Context.active.env['LANG']

                dlb.ex.Context.active.env['LANG'] = 'de_CH'
                with self.assertRaises(ValueError):
                    dlb.ex.Context.active.env['LANG'] = 'fr_FR'  # would raise ValueError

            self.assertEqual(dlb.ex.Context.active.env['LANG'], 'de_AT')
            del dlb.ex.Context.active.env['LANG']  # undefine 'LANG'
            self.assertNotIn('LANG', dlb.ex.Context.active.env)
            dlb.ex.Context.active.env['LANG'] = 'fr_FR'  # ok
