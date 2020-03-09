# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex
from dlb.ex import Tool
import unittest


class ImportTest(unittest.TestCase):

    def test_all_is_correct(self):
        import dlb.ex.tool
        self.assertEqual({
            'Tool',
            'DefinitionAmbiguityError',
            'DependencyRoleAssignmentError',
            'DependencyCheckError',
            'ExecutionParameterError',
            'RedoError'},
            set(dlb.ex.tool.__all__))
        self.assertTrue('Tool' in dir(dlb.ex))


class InheritanceTest(unittest.TestCase):

    def test_hierarchy_matches_nesting(self):
        self.assertTrue(issubclass(Tool.Input, Tool.Dependency))
        self.assertTrue(issubclass(Tool.Input.RegularFile, Tool.Input))
        self.assertTrue(issubclass(Tool.Input.NonRegularFile, Tool.Input))
        self.assertTrue(issubclass(Tool.Input.Directory, Tool.Input))
        self.assertTrue(issubclass(Tool.Input.EnvVar, Tool.Input))

        self.assertTrue(issubclass(Tool.Output, Tool.Dependency))
        self.assertTrue(issubclass(Tool.Output.RegularFile, Tool.Output))
        self.assertTrue(issubclass(Tool.Output.NonRegularFile, Tool.Output))
        self.assertTrue(issubclass(Tool.Output.Directory, Tool.Output))


class AttributeDefineTest(unittest.TestCase):

    def test_can_define_execution_parameter(self):
        # noinspection PyUnusedLocal,PyAbstractClass
        class ATool(Tool):
            """Hohoho"""
            X = 2
            X_Y_Z = '?'
            A3_B = None
        del ATool

    def test_can_define_dependency(self):
        # noinspection PyUnusedLocal,PyAbstractClass
        class ATool(Tool):
            source_file = Tool.Input.RegularFile()
            object_file = Tool.Output.RegularFile()
        del ATool

    def test_can_define_classmethod(self):
        # noinspection PyUnusedLocal,PyAbstractClass
        class ATool(Tool):
            pass
        del ATool

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_cannot_define_other(self):
        tmpl = (
            "invalid class attribute name: {}\n"
            "  | every class attribute of a 'dlb.ex.Tool' must be named like 'UPPER_CASE_WORD' or 'lower_case_word"
        )
        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                _X = 2
        self.assertEqual(str(cm.exception), tmpl.format(repr('_X')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                X_ = '?'
        self.assertEqual(str(cm.exception), tmpl.format(repr('X_')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                X__Y = None
        self.assertEqual(str(cm.exception), tmpl.format(repr('X__Y')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                X_y_Z = None
        self.assertEqual(str(cm.exception), tmpl.format(repr('X_y_Z')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                _x = None
        self.assertEqual(str(cm.exception), tmpl.format(repr('_x')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                x_ = None
        self.assertEqual(str(cm.exception), tmpl.format(repr('x_')))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_noncallable_attribute_must_be_concrete_dependency(self):
        msg = "the value of 'x_y_z' must be callable or an instance of a concrete subclass of 'dlb.ex.Tool.Dependency'"

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = None
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = Tool.Dependency()
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = Tool.Dependency[:]()
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_callable_attribute_must_not_have_different_signature(self):
        class ATool(Tool):
            # noinspection PyUnusedLocal
            def x_y_z(self, s: str) -> int:  # ok, not in a base class
                return 0

            async def u_v(self):  # ok, not in a base class
                return 0

            a = Tool.Input.RegularFile()

        class BTool(ATool):
            def x_y_z(self, s: str) -> int:  # ok, same signature in base class
                return 1

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                # noinspection PyMethodOverriding
                def x_y_z(self) -> int:  # not ok, different signature in base class
                    return 1
        msg = "the value of 'x_y_z' must be an callable with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                async def x_y_z(self, s: str) -> int:  # not ok, not a coroutine function in base class
                    return 1
        msg = "the value of 'x_y_z' must be an callable that is not a coroutine function"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                def u_v(self):  # not ok, coroutine function in base class
                    return 0
        msg = "the value of 'u_v' must be an coroutine function (defined with 'async def')"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class FTool(ATool):
                u_v = Tool.Input.RegularFile()
        regex = r"\A()the value of 'u_v' must be callable since it is callable in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

        with self.assertRaises(TypeError) as cm:
            class GTool(ATool):
                def a(self):
                    pass
        regex = r"\A()the value of 'a' must not be callable since it is not callable in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

        with self.assertRaises(TypeError) as cm:
            class HTool(ATool):
                u_v = 27
        msg = "the value of 'u_v' must be callable or an instance of a concrete subclass of 'dlb.ex.Tool.Dependency'"
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_some_methods_cannot_be_overridden(self):
        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __new__(cls):
                    pass
        self.assertEqual("must not be overridden in a 'dlb.ex.Tool': '__new__'", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            # noinspection PyMissingConstructor
            class ATool(Tool):
                def __init__(self):
                    pass
        self.assertEqual("must not be overridden in a 'dlb.ex.Tool': '__init__'", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __setattr__(self, name, value):
                    pass
        self.assertEqual("must not be overridden in a 'dlb.ex.Tool': '__setattr__'", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __delattr__(self, name):
                    pass
        self.assertEqual("must not be overridden in a 'dlb.ex.Tool': '__delattr__'", str(cm.exception))

    # noinspection PyAbstractClass
    def test_can_inherit_invalid_from_nontool(self):
        class ATool(Tool):
            pass

        class X:
            _X_y_Z = None
            a_b_c = 1

        class BTool(ATool, X):
            pass

        self.assertEqual(BTool.a_b_c, 1)


class ExecutionParameterOverridingTest(unittest.TestCase):

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_be_overridden_with_same_type(self):
        class ATool(Tool):
            X = 1

        class BTool(ATool):
            X = 2

        self.assertNotEqual(ATool.X, BTool.X)

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                X = ''
        self.assertEqual(
            str(cm.exception),
            "attribute 'X' of base class may only be overridden with a value which is a <class 'int'>")


class DependencyRuleOverridingTest(unittest.TestCase):

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_override_with_same(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile()

        class BTool(ATool):
            source_file = Tool.Input.RegularFile()

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_cannot_override_input_with_output(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_file = Tool.Output.RegularFile()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_cannot_override_file_with_director(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_file = Tool.Input.Directory()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_path_with_more_restrictive_path(self):
        import dlb.fs

        class ATool(Tool):
            source_file = Tool.Input.RegularFile()

        class BTool(ATool):  # ok, cls is more restrictive
            source_file = Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath)

        with self.assertRaises(TypeError) as cm:
            class DTool(BTool):  # cls is less restrictive
                source_file = Tool.Input.RegularFile()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_nonrequired_with_required(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile(required=False)

        class BTool(ATool):  # ok, required=True is more restrictive than required=False
            source_file = Tool.Input.RegularFile(required=True)

        with self.assertRaises(TypeError) as cm:
            class CTool(BTool):
                source_file = Tool.Input.RegularFile(required=False)
        self.assertRegex(
            r"^attribute 'source_file' of base class may only be overridden by a "
            r"<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive$",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_with_similar_multiplicity(self):
        class ATool(Tool):
            source_files = Tool.Input.RegularFile[1:]()
            linked_file = Tool.Output.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_files = Tool.Input.RegularFile()
        self.assertEqual(
            "attribute 'source_files' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                linked_file = Tool.Output.RegularFile[:]()
        self.assertEqual(
            "attribute 'linked_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Output.RegularFile'> at least as restrictive",
            str(cm.exception))


class WriteProtectionTest(unittest.TestCase):

    # noinspection PyAbstractClass
    def test_class_attributes_are_not_writable(self):
        class ATool(Tool):
            A = 1
            x_y_z = Tool.Input.RegularFile()

        t = Tool()

        with self.assertRaises(AttributeError):
            ATool.A = 2

        with self.assertRaises(AttributeError):
            ATool.x_y_z = 2

        with self.assertRaises(AttributeError):
            t.u = 3

        with self.assertRaises(AttributeError):
            del ATool.A

        with self.assertRaises(AttributeError):
            del ATool.x_y_z

        with self.assertRaises(AttributeError):
            del t.u
