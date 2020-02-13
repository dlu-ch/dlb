# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import dlb.fs
import dlb.ex
from dlb.ex import Tool
import pathlib
import tempfile
import zipfile
import unittest
import tools_for_test


class ImportTest(unittest.TestCase):

    def test_all_is_correct(self):
        import dlb.ex.tool
        self.assertEqual({
            'Tool',
            'DefinitionAmbiguityError',
            'DependencyRoleAssignmentError'},
            set(dlb.ex.tool.__all__))
        self.assertTrue('Tool' in dir(dlb.ex))


class InheritanceTest(unittest.TestCase):

    def test_hierarchy_matches_nesting(self):
        self.assertTrue(issubclass(Tool.Input, Tool.Dependency))
        self.assertTrue(issubclass(Tool.Input.RegularFile, Tool.Input))
        self.assertTrue(issubclass(Tool.Input.NonRegularFile, Tool.Input))
        self.assertTrue(issubclass(Tool.Input.Directory, Tool.Input))
        self.assertTrue(issubclass(Tool.Input.EnvVar, Tool.Input))

        self.assertTrue(issubclass(Tool.Intermediate, Tool.Dependency))

        self.assertTrue(issubclass(Tool.Output, Tool.Dependency))
        self.assertTrue(issubclass(Tool.Output.RegularFile, Tool.Output))
        self.assertTrue(issubclass(Tool.Output.NonRegularFile, Tool.Output))
        self.assertTrue(issubclass(Tool.Output.Directory, Tool.Output))


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
        msg = "the value of 'x_y_z' must be an instance of a concrete subclass of 'dlb.ex.Tool.Dependency'"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = Tool.Dependency()
        msg = "the value of 'x_y_z' must be an instance of a concrete subclass of 'dlb.ex.Tool.Dependency'"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ATool(Tool):
                x_y_z = Tool.Dependency[:]()

    # noinspection PyUnusedLocal,PyRedeclaration
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
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal
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
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal
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

    # noinspection PyUnusedLocal
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
        log_file = Tool.Output.RegularFile(required=True, explicit=False)

    class CTool(Tool):
        envvar = Tool.Input.EnvVar(restriction='.*', example='', required=False)

    def test_tool_can_be_constructed_without_arguments(self):
        Tool()

    def test_dependencies_are_assigned(self):
        t = ConstructionTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual(t.source_file, 'x.cpp')
        self.assertEqual(t.object_file, 'x.cpp.o')
        self.assertIsNone(t.map_file)

        self.assertIsInstance(ConstructionTest.BTool.source_file, Tool.Input)
        self.assertIsInstance(ConstructionTest.BTool.object_file, Tool.Output)
        self.assertIsInstance(ConstructionTest.BTool.map_file, Tool.Output)

    def test_must_have_argument_for_required_explicit_dependency(self):
        with self.assertRaises(dlb.ex.DependencyRoleAssignmentError) as cm:
            ConstructionTest.BTool(source_file='x.cpp')
        msg = "missing keyword argument for required and explicit dependency role: 'object_file'"
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(dlb.ex.DependencyRoleAssignmentError) as cm:
            ConstructionTest.BTool(source_file=None)
        msg = "keyword argument for required dependency role must not be None: 'source_file'"
        self.assertEqual(msg, str(cm.exception))

    def test_must_not_have_argument_for_undeclared_dependency(self):
        msg = (
            "keyword argument does not name a dependency role of 'ConstructionTest.BTool': 'temporary_file'\n"
            "  | dependency roles: 'source_file', 'log_file', 'object_file', 'map_file'"
        )

        with self.assertRaises(dlb.ex.DependencyRoleAssignmentError) as cm:
            ConstructionTest.BTool(temporary_file='x.cpp.o._')
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(dlb.ex.DependencyRoleAssignmentError) as cm:
            ConstructionTest.BTool(temporary_file=None)
        self.assertEqual(msg, str(cm.exception))

    def test_must_not_have_argument_for_nonexplicit_dependencies(self):
        msg = (
            "keyword argument does name a non-explicit dependency role: 'log_file'\n"
            "  | non-explicit dependency must not be assigned at construction"
        )

        with self.assertRaises(dlb.ex.DependencyRoleAssignmentError) as cm:
            ConstructionTest.BTool(log_file='x.log')
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(dlb.ex.DependencyRoleAssignmentError) as cm:
            ConstructionTest.BTool(log_file=None)
        self.assertEqual(msg, str(cm.exception))


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

    def test_name_matches_class(self):
        self.assertEqual(Tool.__name__, 'Tool')
        self.assertEqual(Tool.Dependency.__name__, 'Dependency')
        self.assertEqual(Tool.Input.__name__, 'Input')
        self.assertEqual(Tool.Intermediate.__name__, 'Intermediate')
        self.assertEqual(Tool.Output.__name__, 'Output')

    def test_repr_name_reflects_recommended_module(self):
        self.assertEqual(repr(Tool), "<class 'dlb.ex.Tool'>")

    def test_repr_name_reflects_nesting(self):
        self.assertEqual(repr(Tool.Dependency), "<class 'dlb.ex.Tool.Dependency'>")
        self.assertEqual(repr(Tool.Input), "<class 'dlb.ex.Tool.Input'>")
        self.assertEqual(repr(Tool.Input.RegularFile), "<class 'dlb.ex.Tool.Input.RegularFile'>")
        self.assertEqual(repr(Tool.Output), "<class 'dlb.ex.Tool.Output'>")
        self.assertEqual(repr(Tool.Output.RegularFile), "<class 'dlb.ex.Tool.Output.RegularFile'>")
        self.assertEqual(repr(Tool.Intermediate), "<class 'dlb.ex.Tool.Intermediate'>")

    def test_shows_name_and_dependency_rules(self):
        self.assertEqual(repr(Tool()), 'Tool()')

        t = ReprTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        text = "ReprTest.BTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'), map_file=None)"
        self.assertEqual(text, repr(t))

        class CTool(Tool):
            pass

        self.assertEqual("ReprTest.test_shows_name_and_dependency_rules.<locals>.CTool()", repr(CTool()))

    def test_inherit_invalid_from_nontool(self):
        t = ReprTest.DTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual("ReprTest.DTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'))", repr(t))


class AmbiguityTest(tools_for_test.TemporaryDirectoryTestCase):
    def test_location_of_tools_are_correct(self):
        lineno = 429  # of this line

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
            # noinspection PyUnresolvedReferences
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

    # noinspection PyUnusedLocal,PyPep8Naming
    def test_definition_fails_for_two_different_dynamic_definitions(self):
        def f(s):
            class A(Tool):
                X = 1 if s else 2
            return A

        regex = (
            r"(?m)"
            r"\Ainvalid tool definition: another 'Tool' class was defined on the same source file line\n"
            r"  \| location: '.+':[0-9]+\n"
            r"  \| class: <class '.+'>\Z"
        )

        B = f(False)
        with self.assertRaisesRegex(dlb.ex.DefinitionAmbiguityError, regex):
            C = f(True)

    def test_definition_fails_for_two_equal_dynamic_definitions(self):
        # noinspection PyUnusedLocal
        def f(s):
            class A(Tool):
                pass
            return A

        regex = (
            r"(?m)"
            r"\Ainvalid tool definition: another 'Tool' class was defined on the same source file line\n"
            r"  \| location: '.+':[0-9]+\n"
            r"  \| class: <class '.+'>\Z"
        )
        with self.assertRaisesRegex(dlb.ex.DefinitionAmbiguityError, regex):
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
        with self.assertRaisesRegex(dlb.ex.DefinitionAmbiguityError, regex):
            # noinspection PyUnresolvedReferences
            import z  # needs a name different from the already loaded modules
        del sys.path[0]


class DependencyActionRegistrationTest(unittest.TestCase):

    def test_fails_for_unregistered_dependency_class(self):
        class D(dlb.ex.Tool.Input.RegularFile):
            pass

        class T(dlb.ex.Tool):
            oho = D()

        regex = r"keyword names unregistered dependency class <class '.+'>: 'oho'"
        with self.assertRaisesRegex(dlb.ex.DependencyRoleAssignmentError, regex):
            T(oho='x')


class ToolInstanceFingerprintTest(unittest.TestCase):

    class ATool(Tool):
        source_file = Tool.Input.RegularFile[:]()
        object_file = Tool.Output.RegularFile(required=False)
        map_file = Tool.Output.RegularFile(required=False)

    def test_is_equal_for_same_concrete_dependencies(self):
        tool1 = ToolInstanceFingerprintTest.ATool(source_file=['src/a/b.c', 'src/d.c'], object_file=pathlib.PosixPath('e.o'))
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

    def test_is_20_byte(self):
        tool = ToolInstanceFingerprintTest.ATool(source_file=[], object_file='e.o')
        self.assertIsInstance(tool.fingerprint, bytes)
        self.assertEqual(20, len(tool.fingerprint))

    def test_is_readonly(self):
        tool = ToolInstanceFingerprintTest.ATool(source_file=[], object_file='e.o')
        with self.assertRaises(AttributeError):
            tool.fingerprint = b''
