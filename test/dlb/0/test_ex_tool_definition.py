# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import testenv  # also sets up module search paths
import dlb.fs
import dlb.ex
import sys
import os.path
import pathlib
import time
import tempfile
import zipfile
import importlib.util
import unittest


class RegexTest(unittest.TestCase):

    def test_uppercase_word(self):
        import dlb.ex._tool
        self.assertTrue(dlb.ex._tool.UPPERCASE_NAME_REGEX.match('A'))
        self.assertTrue(dlb.ex._tool.UPPERCASE_NAME_REGEX.match('A2_B'))
        self.assertFalse(dlb.ex._tool.UPPERCASE_NAME_REGEX.match('_A'))

    def test_lowercase_word(self):
        import dlb.ex._tool
        self.assertTrue(dlb.ex._tool.LOWERCASE_MULTIWORD_NAME_REGEX.match('object_file'))
        self.assertFalse(dlb.ex._tool.LOWERCASE_MULTIWORD_NAME_REGEX.match('object'))
        self.assertFalse(dlb.ex._tool.LOWERCASE_MULTIWORD_NAME_REGEX.match('_object_file_'))
        self.assertFalse(dlb.ex._tool.LOWERCASE_MULTIWORD_NAME_REGEX.match('Object_file_'))


class ToolClassAttributeDefineTest(unittest.TestCase):

    def test_can_define_execution_parameter(self):
        # noinspection PyUnusedLocal,PyAbstractClass
        class ATool(dlb.ex.Tool):
            """Hohoho"""
            X = 2
            X_Y_Z = '?'
            A3_B = None
        del ATool

    def test_can_define_dependency(self):
        # noinspection PyUnusedLocal,PyAbstractClass
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.input.RegularFile()
            object_file = dlb.ex.output.RegularFile()
        del ATool

    def test_can_define_classmethod(self):
        # noinspection PyUnusedLocal,PyAbstractClass
        class ATool(dlb.ex.Tool):
            pass
        del ATool

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_cannot_define_other(self):
        tmpl = (
            "invalid class attribute name: {}\n"
            "  | every class attribute of a 'dlb.ex.Tool' must be named "
            "like 'UPPER_CASE' or 'lower_case' (at least two words)"
        )
        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                _X = 2
        self.assertEqual(str(cm.exception), tmpl.format(repr('_X')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                X_ = '?'
        self.assertEqual(str(cm.exception), tmpl.format(repr('X_')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                X__Y = None
        self.assertEqual(str(cm.exception), tmpl.format(repr('X__Y')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                X_y_Z = None
        self.assertEqual(str(cm.exception), tmpl.format(repr('X_y_Z')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                _x = None
        self.assertEqual(str(cm.exception), tmpl.format(repr('_x')))

        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                x_ = None
        self.assertEqual(str(cm.exception), tmpl.format(repr('x_')))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_nonmethod_attribute_must_be_concrete_dependency(self):
        msg = "attribute 'x_y_z' must be a method or an instance of a concrete subclass of 'dlb.ex.Dependency'"

        with self.assertRaises(TypeError) as cm:
            class ATool(dlb.ex.Tool):
                x_y_z = None
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ATool(dlb.ex.Tool):
                x_y_z = dlb.ex.Dependency()
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ATool(dlb.ex.Tool):
                x_y_z = dlb.ex.Dependency[:]()
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_attribute_must_be_method_if_in_base(self):
        class ATool(dlb.ex.Tool):
            # noinspection PyUnusedLocal
            def i_m(self, s: str) -> int:
                return 0

            async def a_i_m(self):
                return 0

            @classmethod
            def c_m(cls):
                return 0

            # noinspection PyUnusedLocal
            @classmethod
            async def a_c_m(cls, *, x: int):
                return 0

            # noinspection PyUnusedLocal
            @staticmethod
            def s_m(y: bool):
                return 0

            @staticmethod
            async def a_s_m():
                return 0

            some_thing = dlb.ex.input.RegularFile()

        class BTool(ATool):
            def i_m(self, s: str) -> int:
                return 1

            async def a_i_m(self):
                return 1

            @classmethod
            def c_m(cls):
                return 1

            # noinspection PyUnusedLocal
            @classmethod
            async def a_c_m(cls, *, x: int):
                return 1

            # noinspection PyUnusedLocal
            @staticmethod
            def s_m(y: bool):
                return 1

            @staticmethod
            async def a_s_m():
                return 1

            def other_thing(self):  # not method in base class
                pass

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                i_m = dlb.ex.input.RegularFile()
        regex = r"\A()attribute 'i_m' must be a method since it is a method in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                a_i_m = dlb.ex.input.RegularFile()
        regex = r"\A()attribute 'a_i_m' must be a method since it is a method in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                c_m = dlb.ex.input.RegularFile()
        regex = r"\A()attribute 'c_m' must be a method since it is a method in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                a_c_m = dlb.ex.input.RegularFile()
        regex = r"\A()attribute 'a_c_m' must be a method since it is a method in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                s_m = dlb.ex.input.RegularFile()
        regex = r"\A()attribute 's_m' must be a method since it is a method in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                a_s_m = dlb.ex.input.RegularFile()
        regex = r"\A()attribute 'a_s_m' must be a method since it is a method in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

        with self.assertRaises(TypeError) as cm:
            class HTool(ATool):
                def some_thing(self):
                    pass
        regex = r"\A()attribute 'some_thing' must not be a method since it is not a method in <.*>\Z"
        self.assertRegex(str(cm.exception), regex)

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_method_attribute_must_have_same_signature_as_in_base(self):
        class ATool(dlb.ex.Tool):
            # noinspection PyUnusedLocal
            def x_y(self, s: str) -> int:
                return 0

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                # noinspection PyMethodOverriding
                def x_y(self) -> int:  # not ok, different signature in base class
                    return 1
        msg = "attribute 'x_y' must be a (instance) method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                # noinspection PyMethodOverriding
                @classmethod
                def x_y(self, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a (instance) method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            # noinspection
            class DTool(ATool):
                # noinspection PyMethodOverriding,PyShadowingNames
                @staticmethod
                def x_y(self, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a (instance) method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                async def x_y(self, s: str) -> int:  # not ok, same signature but not a coroutine function in base class
                    return 1
        msg = "attribute 'x_y' must not be a coroutine function (defined with 'async def')"
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_async_method_attribute_must_have_same_signature_as_in_base(self):
        class ATool(dlb.ex.Tool):
            # noinspection PyUnusedLocal
            async def x_y(self, s: str) -> int:
                return 0

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                # noinspection PyMethodOverriding
                async def x_y(self) -> int:  # not ok, different signature in base class
                    return 1
        msg = "attribute 'x_y' must be a (instance) method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                # noinspection PyMethodOverriding
                @classmethod
                async def x_y(self, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a (instance) method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                # noinspection PyMethodOverriding,PyShadowingNames
                @staticmethod
                async def x_y(self, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a (instance) method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                def x_y(self, s: str) -> int:  # not ok, same signature but a coroutine function in base class
                    return 1
        msg = "attribute 'x_y' must be a coroutine function (defined with 'async def')"
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_class_method_attribute_must_have_same_signature_as_in_base(self):
        class ATool(dlb.ex.Tool):
            # noinspection PyUnusedLocal
            @classmethod
            def x_y(self, s: str) -> int:
                return 0

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                # noinspection PyMethodOverriding
                @classmethod
                def x_y(self) -> int:  # not ok, different signature in base class
                    return 1
        msg = "attribute 'x_y' must be a class method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                # noinspection PyMethodOverriding
                def x_y(self, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a class method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                # noinspection PyMethodOverriding,PyShadowingNames
                @staticmethod
                def x_y(self, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a class method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                @classmethod
                async def x_y(self, s: str) -> int:  # not ok, same signature but not a coroutine function in base class
                    return 1
        msg = "attribute 'x_y' must not be a coroutine function (defined with 'async def')"
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_async_class_method_attribute_must_have_same_signature_as_in_base(self):
        class ATool(dlb.ex.Tool):
            # noinspection PyUnusedLocal
            @classmethod
            async def x_y(self, s: str) -> int:
                return 0

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                # noinspection PyMethodOverriding
                @classmethod
                async def x_y(self) -> int:  # not ok, different signature in base class
                    return 1
        msg = "attribute 'x_y' must be a class method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                # noinspection PyMethodOverriding
                async def x_y(self, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a class method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                # noinspection PyMethodOverriding,PyShadowingNames
                @staticmethod
                async def x_y(self, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a class method with this signature: <Signature (self, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                @classmethod
                def x_y(self, s: str) -> int:  # not ok, same signature but a coroutine function in base class
                    return 1
        msg = "attribute 'x_y' must be a coroutine function (defined with 'async def')"
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_static_method_attribute_must_have_same_signature_as_in_base(self):
        class ATool(dlb.ex.Tool):
            # noinspection PyUnusedLocal
            @staticmethod
            def x_y(se, s: str) -> int:
                return 0

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                # noinspection PyMethodOverriding
                @staticmethod
                def x_y(se) -> int:  # not ok, different signature in base class
                    return 1
        msg = "attribute 'x_y' must be a static method with this signature: <Signature (se, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                # noinspection PyMethodOverriding
                def x_y(se, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a static method with this signature: <Signature (se, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                # noinspection PyMethodOverriding
                @classmethod
                def x_y(se, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a static method with this signature: <Signature (se, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                @staticmethod
                async def x_y(se, s: str) -> int:  # not ok, same signature but not a coroutine function in base class
                    return 1
        msg = "attribute 'x_y' must not be a coroutine function (defined with 'async def')"
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_async_static_method_attribute_must_have_same_signature_as_in_base(self):
        class ATool(dlb.ex.Tool):
            # noinspection PyUnusedLocal
            @staticmethod
            async def x_y(se, s: str) -> int:
                return 0

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                # noinspection PyMethodOverriding
                @staticmethod
                async def x_y(se) -> int:  # not ok, different signature in base class
                    return 1
        msg = "attribute 'x_y' must be a static method with this signature: <Signature (se, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                # noinspection PyMethodOverriding
                async def x_y(se, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a static method with this signature: <Signature (se, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                # noinspection PyMethodOverriding
                @classmethod
                async def x_y(se, s: str) -> int:  # not ok, same signature but different method kind in base class
                    return 1
        msg = "attribute 'x_y' must be a static method with this signature: <Signature (se, s: str) -> int>"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ETool(ATool):
                @staticmethod
                def x_y(se, s: str) -> int:  # not ok, same signature but a coroutine function in base class
                    return 1
        msg = "attribute 'x_y' must be a coroutine function (defined with 'async def')"
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_some_methods_cannot_be_overridden(self):
        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                def __new__(cls):
                    pass
        self.assertEqual("must not be overridden in a 'dlb.ex.Tool': '__new__'", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            # noinspection PyMissingConstructor
            class ATool(dlb.ex.Tool):
                def __init__(self):
                    pass
        self.assertEqual("must not be overridden in a 'dlb.ex.Tool': '__init__'", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                def __setattr__(self, name, value):
                    pass
        self.assertEqual("must not be overridden in a 'dlb.ex.Tool': '__setattr__'", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            class ATool(dlb.ex.Tool):
                def __delattr__(self, name):
                    pass
        self.assertEqual("must not be overridden in a 'dlb.ex.Tool': '__delattr__'", str(cm.exception))

    # noinspection PyAbstractClass
    def test_can_inherit_invalid_from_nontool(self):
        class ATool(dlb.ex.Tool):
            pass

        class X:
            _X_y_Z = None
            a_b_c = 1

        class BTool(ATool, X):
            pass

        self.assertEqual(BTool.a_b_c, 1)

    # noinspection PyAbstractClass
    def test_class_attributes_are_not_writable(self):
        class ATool(dlb.ex.Tool):
            A = 1
            x_y_z = dlb.ex.input.RegularFile()

        t = dlb.ex.Tool()

        with self.assertRaises(AttributeError) as cm:
            ATool.A = 2
        self.assertEqual(f"attributes of {ATool!r} are read-only", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            ATool.x_y_z = 2
        self.assertEqual(f"attributes of {ATool!r} are read-only", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            t.u = 3
        self.assertEqual("attributes of <class 'dlb.ex.Tool'> instances are read-only", str(cm.exception))

    # noinspection PyAbstractClass
    def test_class_attributes_cannot_be_deleted(self):
        class ATool(dlb.ex.Tool):
            A = 1
            x_y_z = dlb.ex.input.RegularFile()

        t = dlb.ex.Tool()

        with self.assertRaises(AttributeError) as cm:
            del ATool.A
        self.assertEqual(f"attributes of {ATool!r} cannot be deleted", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            del ATool.x_y_z
        self.assertEqual(f"attributes of {ATool!r} cannot be deleted", str(cm.exception))

        with self.assertRaises(AttributeError) as cm:
            del t.u
        self.assertEqual("attributes of <class 'dlb.ex.Tool'> instances cannot be deleted", str(cm.exception))


class ExecutionParameterOverrideTest(unittest.TestCase):

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_be_overridden_with_same_type(self):
        class ATool(dlb.ex.Tool):
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

    def test_can_only_be_overridden_in_constructor_with_same_type(self):
        # noinspection PyAbstractClass
        class ATool(dlb.ex.Tool):
            X = 1

        with self.assertRaises(TypeError) as cm:
            ATool(X='')
        self.assertEqual(
            str(cm.exception),
            "attribute 'X' of base class may only be overridden with a value which is a <class 'int'>")

        # noinspection PyAbstractClass
        class BTool(ATool):
            pass

        with self.assertRaises(TypeError) as cm:
            BTool(X='')
        self.assertEqual(
            str(cm.exception),
            "attribute 'X' of base class may only be overridden with a value which is a <class 'int'>")


class DependencyRoleOverrideTest(unittest.TestCase):

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_override_with_same(self):
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.input.RegularFile()

        class BTool(ATool):
            source_file = dlb.ex.input.RegularFile()

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_cannot_override_input_with_output(self):
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.input.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_file = dlb.ex.output.RegularFile()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_cannot_override_file_with_director(self):
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.input.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_file = dlb.ex.input.Directory()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_path_with_more_restrictive_path(self):
        import dlb.fs

        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.input.RegularFile()

        class BTool(ATool):  # ok, cls is more restrictive
            source_file = dlb.ex.input.RegularFile(cls=dlb.fs.NoSpacePath)

        with self.assertRaises(TypeError) as cm:
            class DTool(BTool):  # cls is less restrictive
                source_file = dlb.ex.input.RegularFile()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_nonrequired_with_required(self):
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.input.RegularFile(required=False)

        class BTool(ATool):  # ok, required=True is more restrictive than required=False
            source_file = dlb.ex.input.RegularFile(required=True)

        with self.assertRaises(TypeError) as cm:
            class CTool(BTool):
                source_file = dlb.ex.input.RegularFile(required=False)
        self.assertRegex(
            r"^attribute 'source_file' of base class may only be overridden by a "
            r"<class 'dlb.ex.input.RegularFile'> at least as restrictive$",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_with_similar_multiplicity(self):
        class ATool(dlb.ex.Tool):
            source_files = dlb.ex.input.RegularFile[1:]()
            linked_file = dlb.ex.output.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_files = dlb.ex.input.RegularFile()
        self.assertEqual(
            "attribute 'source_files' of base class may only be overridden by a "
            "<class 'dlb.ex.input.RegularFile'> at least as restrictive",
            str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                linked_file = dlb.ex.output.RegularFile[:]()
        self.assertEqual(
            "attribute 'linked_file' of base class may only be overridden by a "
            "<class 'dlb.ex.output.RegularFile'> at least as restrictive",
            str(cm.exception))


class ToolReprTest(unittest.TestCase):

    # noinspection PyAbstractClass
    class ATool(dlb.ex.Tool):
        source_file = dlb.ex.input.RegularFile()
        object_file = dlb.ex.output.RegularFile()

    # noinspection PyAbstractClass
    class BTool(ATool):
        map_file = dlb.ex.output.RegularFile(required=False)

    # noinspection PyAbstractClass
    class CTool(dlb.ex.Tool):
        source_file = dlb.ex.input.RegularFile()

    class X:
        _X_y_Z = None
        a_b_c = 1

    # noinspection PyAbstractClass
    class DTool(CTool, X):
        object_file = dlb.ex.output.RegularFile()

    def test_repr_name_reflects_recommended_module(self):
        self.assertEqual(repr(dlb.ex.Tool), "<class 'dlb.ex.Tool'>")

    # noinspection PyAbstractClass
    def test_shows_name_and_dependency_roles(self):
        self.assertEqual(repr(dlb.ex.Tool()), 'Tool()')

        t = ToolReprTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        text = "ToolReprTest.BTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'), map_file=None)"
        self.assertEqual(text, repr(t))

        class CTool(dlb.ex.Tool):
            pass

        self.assertEqual("ToolReprTest.test_shows_name_and_dependency_roles.<locals>.CTool()", repr(CTool()))

    def test_inherit_invalid_from_nontool(self):
        t = ToolReprTest.DTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual("ToolReprTest.DTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'))", repr(t))


class ToolDefinitionAmbiguityTest(testenv.TemporaryDirectoryTestCase):

    # noinspection PyAbstractClass
    def test_location_of_tools_are_correct(self):
        lineno = 728  # of this line

        class A(dlb.ex.Tool):
            pass

        class B(A):
            pass

        class C(A):
            pass

        self.assertEqual(A.definition_location, (os.path.realpath(__file__), None, lineno + 2))
        self.assertEqual(B.definition_location, (os.path.realpath(__file__), None, lineno + 2 + 3))
        self.assertEqual(C.definition_location, (os.path.realpath(__file__), None, lineno + 2 + 3 + 3))

    def test_location_in_zip_archive_package_is_correct(self):
        module_name = 'single_use_module1'
        self.assertNotIn(module_name, sys.modules)  # needs a name different from all already loaded modules

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
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname=f'{module_name}/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname=f'{module_name}/v.py')

            importlib.invalidate_caches()
            sys.path.insert(0, zip_file_path)
            try:
                # noinspection PyUnresolvedReferences
                import single_use_module1.v
            finally:
                del sys.path[0]

        self.assertEqual((os.path.realpath(zip_file_path), os.path.join(module_name, 'v.py'), 2),
                         single_use_module1.v.A.definition_location)

    def test_fails_for_zip_without_zip_suffix(self):
        module_name = 'single_use_module2'
        self.assertNotIn(module_name, sys.modules)  # needs a name different from all already loaded modules

        with tempfile.TemporaryDirectory() as tmp_dir_path:
            with tempfile.TemporaryDirectory() as content_tmp_dir_path:
                open(os.path.join(content_tmp_dir_path, '__init__.py'), 'w').close()
                with open(os.path.join(content_tmp_dir_path, 'v.py'), 'w') as f:
                    f.write(
                        'import dlb.ex\n'
                        'class A(dlb.ex.Tool): pass'
                    )

                zip_file_path = os.path.join(tmp_dir_path, 'abc.zi')
                with zipfile.ZipFile(zip_file_path, 'w') as z:
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname=f'{module_name}/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname=f'{module_name}/v.py')

            importlib.invalidate_caches()
            sys.path.insert(0, zip_file_path)
            try:
                # noinspection PyUnresolvedReferences
                with self.assertRaises(dlb.ex.DefinitionAmbiguityError) as cm:
                    import single_use_module2.v
            finally:
                del sys.path[0]

        msg = (
            f"invalid tool definition: location of definition is unknown\n"
            f"  | class: <class '{module_name}.v.A'>\n"
            f"  | define the class in a regular file or in a zip archive ending in '.zip'\n"
            f"  | note also the significance of upper and lower case of module search paths "
            f"on case-insensitive filesystems"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_location_in_zip_archive_module_is_correct(self):
        module_name = 'single_use_module3'
        self.assertNotIn(module_name, sys.modules)  # needs a name different from all already loaded modules

        with tempfile.TemporaryDirectory() as tmp_dir_path:
            with tempfile.TemporaryDirectory() as content_tmp_dir_path:
                with open(os.path.join(content_tmp_dir_path, f'{module_name}.py'), 'w') as f:
                    f.write(
                        'import dlb.ex\n'
                        'class A(dlb.ex.Tool): pass'
                    )

                zip_file_path = os.path.join(tmp_dir_path, 'abc.zip')
                with zipfile.ZipFile(zip_file_path, 'w') as z:
                    z.write(os.path.join(content_tmp_dir_path, f'{module_name}.py'), arcname=f'{module_name}.py')

            importlib.invalidate_caches()
            sys.path.insert(0, zip_file_path)
            try:
                # noinspection PyUnresolvedReferences
                import single_use_module3
            finally:
                del sys.path[0]

        self.assertEqual((os.path.realpath(zip_file_path), f'{module_name}.py', 2),
                         single_use_module3.A.definition_location)

    # noinspection PyAbstractClass
    def test_definition_location_is_readonly(self):
        class A(dlb.ex.Tool):
            pass

        self.assertEqual(A.definition_location[0], os.path.realpath(__file__))

        with self.assertRaises(AttributeError):
            A.definition_location = 42

        self.assertEqual(A.definition_location[0], os.path.realpath(__file__))

    def test_fails_on_import_with_relative_search_path_before_python3dot10(self):
        module_name = 'single_use_module4'
        self.assertNotIn(module_name, sys.modules)  # needs a name different from all already loaded modules

        module_file_name = f'{module_name}.py'

        with open(module_file_name, 'x') as f:
            f.write(
                'import dlb.ex\n'
                'class A(dlb.ex.Tool): pass\n'
                'import os.path\n'
                'definition_path, _, _ = A.definition_location\n'
                'if not os.path.isabs(definition_path): raise ValueError("definition_location is relative")'
            )

        sys.path.insert(0, '.')  # !
        importlib.invalidate_caches()
        ok = False
        try:
            regex = (
                r"(?m)\A"
                r"invalid tool definition: location of definition depends on current working directory\n"
                r"  \| class: <class '.+'>\n"
                r"  \| source file: '.+'\n"
                r"  \| make sure the source file is loaded from an absolute path "
                r"\(directy or from a module search path in sys\.path\)\Z"
            )
            try:
                spec = importlib.util.spec_from_file_location(module_name, module_file_name)
                spec.loader.exec_module(importlib.util.module_from_spec(spec))
                # for some reason 'import ...' works differently on Travis CI than local, so avoid it
                ok = True
            except dlb.ex.DefinitionAmbiguityError as e:
                self.assertRegex(str(e), regex)  # < Python 3.10
        finally:
            del sys.path[0]

        if sys.version_info[:2] >= (3, 10):
            self.assertTrue(ok)
        else:
            self.assertFalse(ok)

    def test_fails_for_equal_dynamic_definitions(self):
        # noinspection PyAbstractClass
        def f():
            class A(dlb.ex.Tool):
                pass
            return A

        regex = (
            r"(?m)\A"
            r"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
            r"  \| location: '.+':[0-9]+\n"
            r"  \| class: <class '.+'>\Z"
        )

        f()
        with self.assertRaisesRegex(dlb.ex.DefinitionAmbiguityError, regex):
            f()

    # noinspection PyPep8Naming
    def test_fails_for_dynamic_definitions_with_different_execution_parameters(self):
        def f(s):
            # noinspection PyAbstractClass
            class A(dlb.ex.Tool):
                X = 1 if s else 2
            return A

        regex = (
            r"(?m)\A"
            r"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
            r"  \| location: '.+':[0-9]+\n"
            r"  \| class: <class '.+'>\Z"
        )

        f(False)
        with self.assertRaisesRegex(dlb.ex.DefinitionAmbiguityError, regex):
            f(True)

    def test_fails_for_dynamic_definitions_with_different_baseclass(self):
        # noinspection PyAbstractClass
        class B(dlb.ex.Tool):
            pass

        # noinspection PyUnusedLocal,PyAbstractClass
        def f(s):
            # noinspection PyAbstractClass
            class A(B if s else dlb.ex.Tool):
                pass
            return A

        regex = (
            r"(?m)\A"
            r"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
            r"  \| location: '.+':[0-9]+\n"
            r"  \| class: <class '.+'>\Z"
        )

        f(False)
        with self.assertRaisesRegex(dlb.ex.DefinitionAmbiguityError, regex):
            f(True)

    def test_fails_for_dynamic_definitions_on_same_line(self):
        [
            type('A', (dlb.ex.Tool,), {}),
            type('B', (dlb.ex.Tool,), {})  # ok, on next line!
        ]

        regex = (
            r"(?m)\A"
            r"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
            r"  \| location: '.+':[0-9]+\n"
            r"  \| class: <class '.+'>\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DefinitionAmbiguityError, regex):
            [type('A', (dlb.ex.Tool,), {}), type('B', (dlb.ex.Tool,), {})]


class ToolInstanceConstructionTest(unittest.TestCase):

    # noinspection PyAbstractClass
    class ATool(dlb.ex.Tool):
        X_Y = 2
        source_file = dlb.ex.input.RegularFile()
        object_file = dlb.ex.output.RegularFile()

    # noinspection PyAbstractClass
    class BTool(ATool):
        U_V_W = '?'
        map_file = dlb.ex.output.RegularFile(required=False)
        log_file = dlb.ex.output.RegularFile(required=True, explicit=False)

    # noinspection PyAbstractClass
    class CTool(dlb.ex.Tool):
        env_var = dlb.ex.input.EnvVar(name='n', pattern='.*', example='', required=False)

    # noinspection PyAbstractClass
    class DTool(BTool):
        include_directories = dlb.ex.input.Directory[:](required=False)

    def test_tool_can_be_constructed_without_arguments(self):
        dlb.ex.Tool()

    def test_dependencies_are_assigned(self):
        t = ToolInstanceConstructionTest.DTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual('x.cpp', t.source_file)
        self.assertEqual('x.cpp.o', t.object_file)
        self.assertIsNone(t.include_directories)
        self.assertIsNone(t.map_file)
        self.assertEqual(NotImplemented, t.log_file)

        t = ToolInstanceConstructionTest.DTool(source_file='x.cpp', object_file='x.cpp.o',
                                               include_directories=['src/a/', 'src/b/c/'])
        self.assertEqual((dlb.fs.Path('src/a/'), dlb.fs.Path('src/b/c/')), t.include_directories)

        self.assertIsInstance(ToolInstanceConstructionTest.DTool.source_file, dlb.ex.InputDependency)
        self.assertIsInstance(ToolInstanceConstructionTest.DTool.object_file, dlb.ex.OutputDependency)
        self.assertIsInstance(ToolInstanceConstructionTest.DTool.include_directories, dlb.ex.InputDependency)
        self.assertIsInstance(ToolInstanceConstructionTest.DTool.map_file, dlb.ex.OutputDependency)

    def test_must_have_argument_for_required_explicit_dependency(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            ToolInstanceConstructionTest.BTool(source_file='x.cpp')
        msg = "missing keyword argument for required and explicit dependency role: 'object_file'"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            ToolInstanceConstructionTest.BTool(source_file=None)
        msg = "keyword argument for required dependency role must not be None: 'source_file'"
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_string_when_multiplicity(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            ToolInstanceConstructionTest.DTool(include_directories='abc')
        msg = (
            "keyword argument for dependency role 'include_directories' is invalid: 'abc'\n"
            "  | reason: since dependency has a multiplicity, value must be iterable (other than 'str' or 'bytes')"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_fails_for_duplicate(self):
        with self.assertRaises(dlb.ex.DependencyError) as cm:
            ToolInstanceConstructionTest.DTool(include_directories=['i/', 'i/'])
        msg = (
            "keyword argument for dependency role 'include_directories' is invalid: ['i/', 'i/']\n"
            "  | reason: iterable must be duplicate-free but contains Path('i/') more than once"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_must_not_have_argument_for_undeclared_dependency(self):
        msg = (
            "keyword argument does not name a dependency role or execution parameter "
            "of 'Tool': 'temporary_file'\n"
            "  | dependency roles: -\n"
            "  | execution parameters: -"
        )

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            dlb.ex.Tool(temporary_file='x.cpp.o._')
        self.assertEqual(msg, str(cm.exception))

        msg = (
            "keyword argument does not name a dependency role or execution parameter "
            "of 'ToolInstanceConstructionTest.BTool': 'temporary_file'\n"
            "  | dependency roles: 'source_file', 'log_file', 'object_file', 'map_file'\n"
            "  | execution parameters: 'U_V_W', 'X_Y'"
        )

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            ToolInstanceConstructionTest.BTool(temporary_file='x.cpp.o._')
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            ToolInstanceConstructionTest.BTool(temporary_file=None)
        self.assertEqual(msg, str(cm.exception))

    def test_must_not_have_argument_for_nonexplicit_dependencies(self):
        msg = (
            "keyword argument does name a non-explicit dependency role: 'log_file'\n"
            "  | non-explicit dependency must not be assigned at construction"
        )

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            ToolInstanceConstructionTest.BTool(log_file='x.log')
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(dlb.ex.DependencyError) as cm:
            ToolInstanceConstructionTest.BTool(log_file=None)
        self.assertEqual(msg, str(cm.exception))

    def test_execution_parameters_are_assigned(self):
        tool = ToolInstanceConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o', U_V_W='!')
        self.assertEqual(2, tool.X_Y)  # unchanged
        self.assertEqual('!', tool.U_V_W)

        tool = ToolInstanceConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o', X_Y=3)
        self.assertEqual(3, tool.X_Y)  # unchanged
        self.assertEqual('?', tool.U_V_W)   # unchanged


class ToolInstanceFingerprintTest(unittest.TestCase):

    # noinspection PyAbstractClass
    class ATool(dlb.ex.Tool):
        source_file = dlb.ex.input.RegularFile[:]()
        object_file = dlb.ex.output.RegularFile(required=False)
        map_file = dlb.ex.output.RegularFile(required=False)
        X = 'blabliblu'

    def test_is_equal_for_same_concrete_dependencies(self):
        tool1 = ToolInstanceFingerprintTest.ATool(source_file=['src/a/b.c', 'src/d.c'],
                                                  object_file=pathlib.Path('e.o'))
        tool2 = ToolInstanceFingerprintTest.ATool(source_file=['src/a/b.c', dlb.fs.Path('src/d.c')], object_file='e.o')
        self.assertEqual(tool1.fingerprint, tool2.fingerprint)

    def test_is_equal_for_different_argument_order(self):
        tool1 = ToolInstanceFingerprintTest.ATool(source_file=['src/a/b.c'], object_file='e.o', map_file='e.map')
        tool2 = ToolInstanceFingerprintTest.ATool(map_file='e.map', source_file=['src/a/b.c'], object_file='e.o')
        self.assertEqual(tool1.fingerprint, tool2.fingerprint)

    def test_is_not_equal_for_different_concrete_dependencies(self):
        tool1 = ToolInstanceFingerprintTest.ATool(source_file=['src/a/b.c', 'src/d.c'], object_file='e.o')
        tool2 = ToolInstanceFingerprintTest.ATool(source_file=['src/d.c'], object_file='e.o')
        self.assertNotEqual(tool1.fingerprint, tool2.fingerprint)

        tool1 = ToolInstanceFingerprintTest.ATool(source_file=['src/a/b.c'], object_file='e.o', map_file='e.map')
        tool2 = ToolInstanceFingerprintTest.ATool(source_file=['src/a/b.c'], map_file='e.o', object_file='e.mp')
        self.assertNotEqual(tool1.fingerprint, tool2.fingerprint)

    def test_is_equal_for_same_execution_parameters(self):
        tool1 = ToolInstanceConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        tool2 = ToolInstanceConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o',
                                                   X_Y=ToolInstanceConstructionTest.BTool.X_Y)
        self.assertEqual(tool1.fingerprint, tool2.fingerprint)

    def test_is_not_equal_for_different_execution_parameters(self):
        tool1 = ToolInstanceConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        tool2 = ToolInstanceConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o', U_V_W='!')
        tool3 = ToolInstanceConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o', X_Y=3)
        tool4 = ToolInstanceConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o',
                                                   X_Y=ToolInstanceConstructionTest.BTool.X_Y)
        self.assertNotEqual(tool1.fingerprint, tool2.fingerprint)
        self.assertNotEqual(tool1.fingerprint, tool3.fingerprint)
        self.assertEqual(tool1.fingerprint, tool4.fingerprint)

    def test_is_reproducible(self):
        tool = ToolInstanceFingerprintTest.ATool(source_file=[], object_file='e.o')
        fingerprint1 = tool.fingerprint
        self.assertEqual(fingerprint1, tool.fingerprint)

    def test_is_20_byte(self):
        tool = ToolInstanceFingerprintTest.ATool(source_file=[], object_file='e.o')
        self.assertIsInstance(tool.fingerprint, bytes)
        self.assertEqual(20, len(tool.fingerprint))

    def test_is_not_writable(self):
        tool = ToolInstanceFingerprintTest.ATool(source_file=[], object_file='e.o')
        with self.assertRaises(AttributeError) as cm:
            # noinspection PyPropertyAccess
            tool.fingerprint = b''
        self.assertEqual(f"attributes of {tool.__class__!r} "
                         f"instances are read-only", str(cm.exception))


class ToolRegistryTest(testenv.TemporaryWorkingDirectoryTestCase):

    def test_fails_for_nontool(self):
        class A:
            pass

        with dlb.ex.Context():
            with self.assertRaises(TypeError):
                dlb.ex._tool.get_and_register_tool_info(A)

    # noinspection PyAbstractClass
    def test_path_for_tool_is_absolute(self):
        class A(dlb.ex.Tool):
            pass

        with dlb.ex.Context():
            info = dlb.ex._tool.get_and_register_tool_info(A)

        p = os.path.realpath(__file__)
        self.assertGreater(len(info.permanent_local_tool_id), 1)

        for p in info.definition_paths:
            self.assertTrue(os.path.isabs(p), p)
        self.assertTrue(p in info.definition_paths, [p, info.definition_paths])

    def test_path_of_tools_defined_in_managed_tree_are_correct(self):
        module_name = 'single_use_module5'
        self.assertNotIn(module_name, sys.modules)  # needs a name different from all already loaded modules

        os.mkdir('a')
        open(os.path.join('a', '__init__.py'), 'x').close()
        with open(os.path.join('a', 'u.py'), 'x') as f:
            f.write(
                'import dlb.ex\n'
                'class A(dlb.ex.Tool): pass\n'
                'class B: pass\n'
                'class C(A, B): pass\n'
            )

        with open('v.py', 'x') as f:
            f.write(
                'class D: pass\n'
            )

        with open(f'{module_name}.py', 'x') as f:
            f.write(
                'import a.u\n'
                'import v\n'
                'class E(a.u.C, v.D): pass\n'
            )

        importlib.invalidate_caches()
        sys.path.insert(0, os.getcwd())
        try:
            # noinspection PyUnresolvedReferences
            import single_use_module5
        finally:
            del sys.path[0]

        with dlb.ex.Context():
            t = time.monotonic_ns()
            info1 = dlb.ex._tool.get_and_register_tool_info(single_use_module5.E)
            dt1 = time.monotonic_ns() - t

            t = time.monotonic_ns()
            info2 = dlb.ex._tool.get_and_register_tool_info(single_use_module5.E)
            dt2 = time.monotonic_ns() - t

        print(f'get_and_register_tool_info(): {dt1/1e3:.0f} us (first call), {dt2/1e3:.0f} us (second call)')

        self.assertIsInstance(info1.permanent_local_tool_id, bytes)
        self.assertGreater(len(info1.permanent_local_tool_id), 1)

        p1 = os.path.realpath(os.path.join(os.getcwd(), 'a', 'u.py'))
        p2 = os.path.realpath(os.path.join(os.getcwd(), f'{module_name}.py'))
        self.assertEqual(3, len(info1.definition_paths), info1.definition_paths)  # incl. _tool.py
        self.assertTrue(p1 in info1.definition_paths)
        self.assertTrue(p2 in info1.definition_paths)
        self.assertEqual(info1, info2)


class DependencyActionRegistrationTest(unittest.TestCase):

    # noinspection PyAbstractClass
    def test_fails_for_unregistered_dependency_class(self):
        class D(dlb.ex.input.RegularFile):
            pass

        class T(dlb.ex.Tool):
            o_ho = D()

        regex = r"keyword names unregistered dependency class <class '.+'>: 'o_ho'"
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            T(o_ho='x')
