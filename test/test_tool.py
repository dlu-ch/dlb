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


class DependencyInheritanceTest(unittest.TestCase):

    def test_hierarchy_matches_nesting(self):
        self.assertTrue(issubclass(Tool.Input, Tool.Dependency))
        self.assertTrue(issubclass(Tool.Input.RegularFile, Tool.Input))

        self.assertTrue(issubclass(Tool.Output, Tool.Dependency))
        self.assertTrue(issubclass(Tool.Output.RegularFile, Tool.Output))


class DependencyReprTest(unittest.TestCase):

    def test_name_matches_class(self):
        self.assertEqual(Tool.Dependency.__name__, 'Dependency')
        self.assertEqual(Tool.Input.__name__, 'Input')

    def test_name_matches_nesting(self):
        self.assertEqual(repr(Tool.Dependency), "<class 'dlb.cmd.tool.Tool.Dependency'>")
        self.assertEqual(repr(Tool.Input), "<class 'dlb.cmd.tool.Tool.Input'>")
        self.assertEqual(repr(Tool.Input.RegularFile), "<class 'dlb.cmd.tool.Tool.Input.RegularFile'>")
        self.assertEqual(repr(Tool.Output), "<class 'dlb.cmd.tool.Tool.Output'>")
        self.assertEqual(repr(Tool.Output.RegularFile), "<class 'dlb.cmd.tool.Tool.Output.RegularFile'>")
        self.assertEqual(repr(Tool.Intermediate), "<class 'dlb.cmd.tool.Tool.Intermediate'>")


class DependencyValidationTest(unittest.TestCase):

    def test_abstract_dependency_validation_raises(self):
        with self.assertRaises(NotImplementedError):
            Tool.Dependency().validate(0)
        with self.assertRaises(NotImplementedError):
            Tool.Input().validate(0)
        with self.assertRaises(NotImplementedError):
            Tool.Intermediate().validate(0)
        with self.assertRaises(NotImplementedError):
            Tool.Output().validate(0)

    def test_non_is_not_valid_for_required(self):
        self.assertIsNone(Tool.Input.RegularFile(is_required=False).validate(None))
        with self.assertRaises(ValueError) as cm:
            Tool.Input.RegularFile(is_required=True).validate(None)
        self.assertEqual(str(cm.exception), 'required dependency must not be None')

        self.assertIsNone(Tool.Output.Directory(is_required=False).validate(None))
        with self.assertRaises(ValueError) as cm:
            Tool.Output.Directory(is_required=True).validate(None)
        self.assertEqual(str(cm.exception), 'required dependency must not be None')

    def test_path_dependency_returns_path(self):
        import dlb.fs

        self.assertEqual(Tool.Input.RegularFile().validate('a/b'), dlb.fs.Path('a/b'))
        self.assertEqual(Tool.Input.Directory().validate('a/b/'), dlb.fs.Path('a/b/'))

        self.assertEqual(Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath).validate('a/b'), dlb.fs.NoSpacePath('a/b'))
        with self.assertRaises(ValueError):
            Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath).validate('a /b')

    def test_dir_is_not_valid_for_non_dir_dependency(self):
        with self.assertRaises(ValueError) as cm:
            Tool.Input.RegularFile().validate('a/b/')
        self.assertEqual(str(cm.exception), "directory path not valid for non-directory dependency: Path('a/b/')")

        with self.assertRaises(ValueError) as cm:
            Tool.Input.Directory().validate('a/b')
        self.assertEqual(str(cm.exception), "non-directory path not valid for directory dependency: Path('a/b')")


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

    # noinspection PyUnusedLocal,PyRedeclaration
    def test_some_methods_cannot_be_overridden(self):
        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __new__(self):
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
        self.assertRegex(
            str(cm.exception),
            r"^attribute 'X' of base class may only be overridden with a value which is a <class 'int'>$")


class DependencyRuleOverridingTest(unittest.TestCase):

    # noinspection PyUnusedLocal,PyRedeclaration
    def test_can_only_be_overridden_with_more_restrictive(self):
        import dlb.fs

        class ATool(Tool):
            source_file = Tool.Input.RegularFile()

        class BTool(ATool):
            source_file = Tool.Input.RegularFile()

        class CTool(ATool):  # ok, cls is more restrictive
            source_file = Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath)

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                source_file = Tool.Output.RegularFile()
        self.assertRegex(
            str(cm.exception),
            r"^attribute 'source_file' of base class may only be overridden by a "
            r"<class 'dlb.cmd.tool.Tool.Input.RegularFile'> at least as restrictive$")

        with self.assertRaises(TypeError) as cm:
            class DTool(ATool):
                source_file = Tool.Input.Directory()
        self.assertRegex(
            str(cm.exception),
            r"^attribute 'source_file' of base class may only be overridden by a "
            r"<class 'dlb.cmd.tool.Tool.Input.RegularFile'> at least as restrictive$")

        with self.assertRaises(TypeError) as cm:
            class DTool(CTool):  # cls is less restrictive
                source_file = Tool.Input.RegularFile()
        self.assertRegex(
            str(cm.exception),
            r"^attribute 'source_file' of base class may only be overridden by a "
            r"<class 'dlb.cmd.tool.Tool.Input.RegularFile'> at least as restrictive$")


class DependencyRuleMultiplicityTest(unittest.TestCase):

    # TODO: complete
    def test_xxx(self):
        Tool.Input.Directory(is_required=False).validate(None)
        Tool.Input.Directory[2:](is_required=False).validate(['1/', '2/'])
        Tool.Input.Directory[2](is_required=False).validate(['1/', '2/'])

    def test_element_must_not_be_none_even_if_dependency_role_not_required(self):
        with self.assertRaises(ValueError) as cm:
            Tool.Input.Directory[:](is_required=False).validate([None])
        self.assertEqual(str(cm.exception), 'required dependency must not be None')


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


class ToolReprTest(unittest.TestCase):

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

        t = ToolReprTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual(
            repr(t),
            "ToolReprTest.BTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'), map_file=None)")

        class CTool(Tool):
            pass

        self.assertEqual(repr(CTool()), "ToolReprTest.test_shows_name_and_dependency_rules.<locals>.CTool()")

    def test_inherit_invalid_from_nontool(self):

        t = ToolReprTest.DTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual(repr(t), "ToolReprTest.DTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'))")
