import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

from dlb.cmd.tool import Tool
import unittest


class TestModule(unittest.TestCase):

    def test_import(self):
        import dlb.cmd.tool
        self.assertEqual(['Tool'], dlb.cmd.tool.__all__)
        self.assertTrue('Tool' in dir(dlb.cmd))


class AttributeDefineTest(unittest.TestCase):

    def test_can_define_execution_parameter(self):
        class ATool(Tool):
            """Hohoho"""
            X = 2
            X_Y_Z = '?'
            A3_B = None
        del ATool

    def test_can_define_dependency(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile()
            object_file = Tool.Output.RegularFile()
        del ATool

    def test_can_define_classmethod(self):
        class ATool(Tool):
            pass
        del ATool

    # noinspection PyUnusedLocal,PyRedeclaration
    def test_cannot_define_other(self):
        tmpl = (
            "invalid class attribute name: {} (every class attribute of a 'dlb.cmd.Tool' must be named "
            "like 'UPPER_CASE_WORD' or 'lower_case_word)"
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

    # noinspection PyUnusedLocal,PyRedeclaration
    def test_lowercase_attribute_must_be_concrete_dependency(self):
        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = None
        self.assertEqual(
            str(cm.exception),
            "the value of 'x_y_z' must be an instance of a concrete subclass of 'dlb.cmd.Tool.Dependency'")

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = Tool.Dependency()
        self.assertEqual(
            str(cm.exception),
            "the value of 'x_y_z' must be an instance of a concrete subclass of 'dlb.cmd.Tool.Dependency'")

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = Tool.Dependency[:]()
        self.assertEqual(
            str(cm.exception),
            "the value of 'x_y_z' must be an instance of a concrete subclass of 'dlb.cmd.Tool.Dependency'")

    # noinspection PyUnusedLocal,PyRedeclaration
    def test_some_methods_cannot_be_overridden(self):
        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __new__(cls):
                    pass
        self.assertEqual(str(cm.exception), "must not be overridden in a 'dlb.cmd.Tool': '__new__'")

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __init__(self):
                    pass
        self.assertEqual(str(cm.exception), "must not be overridden in a 'dlb.cmd.Tool': '__init__'")

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __setattr__(self):
                    pass
        self.assertEqual(str(cm.exception), "must not be overridden in a 'dlb.cmd.Tool': '__setattr__'")

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __delattr__(self):
                    pass
        self.assertEqual(str(cm.exception), "must not be overridden in a 'dlb.cmd.Tool': '__delattr__'")

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

    # noinspection PyUnusedLocal
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

    # noinspection PyUnusedLocal
    def test_can_override_with_same(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile()

        class BTool(ATool):
            source_file = Tool.Input.RegularFile()

    # noinspection PyUnusedLocal
    def test_cannot_override_input_with_output(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_file = Tool.Output.RegularFile()
        self.assertEqual(
            str(cm.exception),
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.cmd.tool.Tool.Input.RegularFile'> at least as restrictive")

    # noinspection PyUnusedLocal
    def test_cannot_override_file_with_director(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_file = Tool.Input.Directory()
        self.assertEqual(
            str(cm.exception),
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.cmd.tool.Tool.Input.RegularFile'> at least as restrictive")

    # noinspection PyUnusedLocal
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
            str(cm.exception),
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.cmd.tool.Tool.Input.RegularFile'> at least as restrictive")

    # noinspection PyUnusedLocal
    def test_can_only_override_nonrequired_with_required(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile(is_required=False)

        class BTool(ATool):  # ok, is_required=True is more restrictive than (is_required=False
            source_file = Tool.Input.RegularFile(is_required=True)

        with self.assertRaises(TypeError) as cm:
            class CTool(BTool):
                source_file = Tool.Input.RegularFile(is_required=False)
        self.assertRegex(
            str(cm.exception),
            r"^attribute 'source_file' of base class may only be overridden by a "
            r"<class 'dlb.cmd.tool.Tool.Input.RegularFile'> at least as restrictive$")

    # noinspection PyUnusedLocal
    def test_can_only_override_with_similar_multiplicity(self):
        class ATool(Tool):
            source_files = Tool.Input.RegularFile[1:]()
            linked_file = Tool.Output.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_files = Tool.Input.RegularFile()
        self.assertEqual(
            str(cm.exception),
            "attribute 'source_files' of base class may only be overridden by a "
            "<class 'dlb.cmd.tool.Tool.Input.RegularFile[1:]'> at least as restrictive")

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                linked_file = Tool.Output.RegularFile[:]()
        self.assertEqual(
            str(cm.exception),
            "attribute 'linked_file' of base class may only be overridden by a "
            "<class 'dlb.cmd.tool.Tool.Output.RegularFile'> at least as restrictive")


class WriteProtectionTest(unittest.TestCase):

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


class ConstructionTest(unittest.TestCase):

    class ATool(Tool):
        source_file = Tool.Input.RegularFile()
        object_file = Tool.Output.RegularFile()

    class BTool(ATool):
        map_file = Tool.Output.RegularFile(is_required=False)

    def test_tool_can_be_constructed_without_parameters(self):
        Tool()

    def test_dependencies_are_assigned(self):

        t = ConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual(t.source_file, 'x.cpp')
        self.assertEqual(t.object_file, 'x.cpp.o')
        self.assertIsNone(t.map_file)

        self.assertIsInstance(ConstructionTest.BTool.source_file, Tool.Input)
        self.assertIsInstance(ConstructionTest.BTool.object_file, Tool.Output)
        self.assertIsInstance(ConstructionTest.BTool.map_file, Tool.Output)

    def test_must_have_parameter_for_required_dependencies(self):
        with self.assertRaises(TypeError) as cm:
            ConstructionTest.BTool(source_file='x.cpp')
        self.assertEqual(str(cm.exception), "missing keyword parameter for dependency role: 'object_file'")

    def test_must_not_have_parameter_for_undeclared_dependencies(self):
        with self.assertRaises(TypeError) as cm:
            ConstructionTest.BTool(temporary_file='x.cpp.o._')
        self.assertRegex(
            str(cm.exception),
            r"^'temporary_file' is not a dependency role of .*: "
            r"'source_file', 'object_file', 'map_file'$")


class ReprTest(unittest.TestCase):

    class ATool(Tool):
        source_file = Tool.Input.RegularFile()
        object_file = Tool.Output.RegularFile()

    class BTool(ATool):
        map_file = Tool.Output.RegularFile(is_required=False)

    class CTool(Tool):
        source_file = Tool.Input.RegularFile()

    class X:
        _X_y_Z = None
        a_b_c = 1

    class DTool(CTool, X):
        object_file = Tool.Output.RegularFile()

    def test_shows_name_and_dependency_rules(self):
        self.assertEqual(repr(Tool()), 'Tool()')

        t = ReprTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual(
            repr(t),
            "ReprTest.BTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'), map_file=None)")

        class CTool(Tool):
            pass

        self.assertEqual(repr(CTool()), "ReprTest.test_shows_name_and_dependency_rules.<locals>.CTool()")

    def test_inherit_invalid_from_nontool(self):

        t = ReprTest.DTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual(repr(t), "ReprTest.DTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'))")
