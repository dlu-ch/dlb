import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import tempfile
import zipfile
import dlb.ex.tool
from dlb.ex.tool import Tool
import unittest
import tools_for_test


class TestModule(unittest.TestCase):

    def test_import(self):
        import dlb.ex.tool
        self.assertEqual(['Tool'], dlb.ex.tool.__all__)
        self.assertTrue('Tool' in dir(dlb.ex))


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
            "invalid class attribute name: {} (every class attribute of a 'dlb.ex.Tool' must be named "
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
            "the value of 'x_y_z' must be an instance of a concrete subclass of 'dlb.ex.Tool.DependencyRole'")

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = Tool.DependencyRole()
        self.assertEqual(
            str(cm.exception),
            "the value of 'x_y_z' must be an instance of a concrete subclass of 'dlb.ex.Tool.DependencyRole'")

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = Tool.DependencyRole[:]()

    # noinspection PyUnusedLocal,PyRedeclaration
    def test_some_methods_cannot_be_overridden(self):
        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __new__(cls):
                    pass
        self.assertEqual(str(cm.exception), "must not be overridden in a 'dlb.ex.Tool': '__new__'")

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __init__(self):
                    pass
        self.assertEqual(str(cm.exception), "must not be overridden in a 'dlb.ex.Tool': '__init__'")

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __setattr__(self):
                    pass
        self.assertEqual(str(cm.exception), "must not be overridden in a 'dlb.ex.Tool': '__setattr__'")

        with self.assertRaises(AttributeError) as cm:
            class ATool(Tool):
                def __delattr__(self):
                    pass
        self.assertEqual(str(cm.exception), "must not be overridden in a 'dlb.ex.Tool': '__delattr__'")

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
            "<class 'dlb.ex.tool.Tool.Input.RegularFile'> at least as restrictive")

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
            "<class 'dlb.ex.tool.Tool.Input.RegularFile'> at least as restrictive")

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
            "<class 'dlb.ex.tool.Tool.Input.RegularFile'> at least as restrictive")

    # noinspection PyUnusedLocal
    def test_can_only_override_nonrequired_with_required(self):
        class ATool(Tool):
            source_file = Tool.Input.RegularFile(required=False)

        class BTool(ATool):  # ok, required=True is more restrictive than (required=False
            source_file = Tool.Input.RegularFile(required=True)

        with self.assertRaises(TypeError) as cm:
            class CTool(BTool):
                source_file = Tool.Input.RegularFile(required=False)
        self.assertRegex(
            str(cm.exception),
            r"^attribute 'source_file' of base class may only be overridden by a "
            r"<class 'dlb.ex.tool.Tool.Input.RegularFile'> at least as restrictive$")

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
            "<class 'dlb.ex.tool.Tool.Input.RegularFile[1:]'> at least as restrictive")

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                linked_file = Tool.Output.RegularFile[:]()
        self.assertEqual(
            str(cm.exception),
            "attribute 'linked_file' of base class may only be overridden by a "
            "<class 'dlb.ex.tool.Tool.Output.RegularFile'> at least as restrictive")


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
        map_file = Tool.Output.RegularFile(required=False)

    class CTool(Tool):
        envvar = Tool.Input.EnvVar(name='XYZ', restriction='.*', example='', required=False)

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
        self.assertEqual(str(cm.exception), "missing keyword parameter for required dependency role: 'object_file'")

    def test_must_not_have_parameter_for_undeclared_dependencies(self):
        with self.assertRaises(TypeError) as cm:
            ConstructionTest.BTool(temporary_file='x.cpp.o._')
        self.assertRegex(
            str(cm.exception),
            r"^'temporary_file' is not a dependency role of .*: "
            r"'source_file', 'object_file', 'map_file'$")

    def test_must_envvar_has_initial_of_environment(self):
        os.environ['XYZ'] = 'abc'
        self.assertEqual(ConstructionTest.CTool().envvar, 'abc')

        del os.environ['XYZ']
        self.assertIsNone(ConstructionTest.CTool().envvar)

    def test_must_not_have_parameter_for_role_with_initial(self):
        with self.assertRaises(TypeError) as cm:
            ConstructionTest.CTool(envvar='uvw')
        self.assertEqual(
            str(cm.exception),
            "dependency role 'envvar' with automatic initialization must not be initialized by keyword parameter")


class ReprTest(unittest.TestCase):

    class ATool(Tool):
        source_file = Tool.Input.RegularFile()
        object_file = Tool.Output.RegularFile()

    class BTool(ATool):
        map_file = Tool.Output.RegularFile(required=False)

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


class AmbiguityTest(tools_for_test.TemporaryDirectoryTestCase):
    def test_location_of_tools_are_correct(self):
        lineno = 375  # of this line

        class A(Tool):
            pass

        class B(A):
            pass

        class C(A):
            pass

        self.assertEqual(A.definition_location, (os.path.realpath(__file__), None, lineno + 2))
        self.assertEqual(B.definition_location, (os.path.realpath(__file__), None, lineno + 2 + 3))
        self.assertEqual(C.definition_location, (os.path.realpath(__file__), None, lineno + 2 + 3 + 3))

    def test_location_in_zip_archive_is_correct(self):
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            with tempfile.TemporaryDirectory() as content_tmp_dir_path:
                with open(os.path.join(content_tmp_dir_path, '__init__.py'), 'w'):
                    pass
                with open(os.path.join(content_tmp_dir_path, 'v.py'), 'w') as f:
                    f.write(
                        'import dlb.ex\n'
                        'class A(dlb.ex.Tool): pass'
                    )

                zip_file_path = os.path.join(tmp_dir_path, 'abc.zip')
                with zipfile.ZipFile(zip_file_path, 'w') as z:
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname='u/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname='u/v.py')

            sys.path.insert(0, zip_file_path)
            import u.v
            del sys.path[0]

        self.assertEqual(u.v.A.definition_location, (os.path.realpath(zip_file_path), 'u/v.py', 2))

    def test_definition_location_is_readonly(self):
        class A(Tool):
            pass

        self.assertEqual(A.definition_location[0], os.path.realpath(__file__))

        with self.assertRaises(AttributeError):
            A.definition_location = 42

        self.assertEqual(A.definition_location[0], os.path.realpath(__file__))

    def test_definition_fails_for_two_different_dynamic_definitions(self):
        def f(s):
            class A(Tool):
                X = 1 if s else 2
            return A

        regex = (
            r"(?m)"
            f"\Ainvalid tool definition: another 'Tool' class was defined on the same source file line\n"
            f"  \| location: '.+':[0-9]+\n"
            f"  \| class: <class '.+'>\Z"
        )

        B = f(False)
        with self.assertRaisesRegex(dlb.ex.tool.DefinitionAmbiguityError, regex):
            C = f(True)

    def test_definition_fails_for_two_equal_dynamic_definitions(self):
        def f(s):
            class A(Tool):
                pass
            return A

        regex = (
            r"(?m)"
            f"\Ainvalid tool definition: another 'Tool' class was defined on the same source file line\n"
            f"  \| location: '.+':[0-9]+\n"
            f"  \| class: <class '.+'>\Z"
        )
        with self.assertRaisesRegex(dlb.ex.tool.DefinitionAmbiguityError, regex):
            _, _ = f(False), f(True)

    def test_definition_fails_in_import_with_relative_search_path(self):
        with open(os.path.join('z.py'), 'x') as f:
            f.write(
                'import dlb.ex\n'
                'class A(dlb.ex.Tool): pass\n'
            )

        sys.path.insert(0, '.')  # !
        regex = (
            r"(?m)"
            r"\Ainvalid tool definition: location of definition depends on current working directory\n"
            r"  \| class: <class '.+'>\n"
            r"  \| source file: '.+'\n"
            r"  \| make sure the matching module search path is an absolute path when the defining module is imported\Z"
        )
        with self.assertRaisesRegex(dlb.ex.tool.DefinitionAmbiguityError, regex):
            import z  # needs a name different from the already loaded modules
        del sys.path[0]
