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
import time
import tempfile
import zipfile
import unittest
import tools_for_test


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
        lineno = 144  # of this line

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
            r"(?m)\A"
            r"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
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
            r"(?m)\A"
            r"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
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
            r"(?m)\A"
            r"invalid tool definition: location of definition depends on current working directory\n"
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
        tool1 = ToolInstanceFingerprintTest.ATool(source_file=['src/a/b.c', 'src/d.c'],
                                                  object_file=pathlib.PosixPath('e.o'))
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


class ToolRegistryTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_path_for_tool_defined_out_managed_is_not_available(self):
        class A(dlb.ex.Tool):
            pass

        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            info = dlb.ex.tool.get_and_register_tool_info(A)

        self.assertGreater(len(info.permanent_local_tool_id), 1)
        self.assertEqual(info.definition_paths, set())

    def test_path_of_tools_defined_in_managed_tree_are_correct(self):
        os.mkdir('a')
        with open(os.path.join('a/__init__.py'), 'x'):
            pass
        with open(os.path.join('a/u.py'), 'x') as f:
            f.write(
                'import dlb.ex\n'
                'class A(dlb.ex.Tool): pass\n'
                'class B: pass\n'
                'class C(A, B): pass\n'
            )

        with open(os.path.join('v.py'), 'x') as f:
            f.write(
                'class D: pass\n'
            )

        with open(os.path.join('w.py'), 'x') as f:
            f.write(
                'import a.u\n'
                'import v\n'
                'class E(a.u.C, v.D): pass\n'
            )

        sys.path.insert(0, os.getcwd())
        # noinspection PyUnresolvedReferences
        import w  # needs a name different from the already loaded modules
        del sys.path[0]

        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            t = time.time()
            info1 = dlb.ex.tool.get_and_register_tool_info(w.E)
            dt1 = time.time() - t
            print(f'first time:  {dt1:6f} s')

            t = time.time()
            info2 = dlb.ex.tool.get_and_register_tool_info(w.E)
            dt2 = time.time() - t
            print(f'second time: {dt2:6f} s')

        self.assertIsInstance(info1.permanent_local_tool_id, bytes)
        self.assertGreater(len(info1.permanent_local_tool_id), 1)
        self.assertEqual(info1.definition_paths, {dlb.fs.Path('a/u.py'), dlb.fs.Path('w.py')})
        self.assertEqual(info1, info2)

    def test_definition_fails_in_import_with_relative_search_path(self):
        with open(os.path.join('z.py'), 'x') as f:
            f.write(
                'import dlb.ex\n'
                'class A(dlb.ex.Tool): pass\n'
            )

        sys.path.insert(0, '.')  # !
        with self.assertRaises(dlb.ex.DefinitionAmbiguityError):
            import z  # needs a name different from the already loaded modules
        del sys.path[0]
