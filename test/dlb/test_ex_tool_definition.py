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
import unittest


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
            source_file = dlb.ex.Tool.Input.RegularFile()
            object_file = dlb.ex.Tool.Output.RegularFile()
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
            "  | every class attribute of a 'dlb.ex.Tool' must be named like 'UPPER_CASE_WORD' or 'lower_case_word"
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
    def test_lowercase_noncallable_attribute_must_be_concrete_dependency(self):
        msg = "the value of 'x_y_z' must be callable or an instance of a concrete subclass of 'dlb.ex.Tool.Dependency'"

        with self.assertRaises(TypeError) as cm:
            class ATool(dlb.ex.Tool):
                x_y_z = None
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ATool(dlb.ex.Tool):
                x_y_z = dlb.ex.Tool.Dependency()
        self.assertEqual(msg, str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class ATool(dlb.ex.Tool):
                x_y_z = dlb.ex.Tool.Dependency[:]()
        self.assertEqual(msg, str(cm.exception))

    # noinspection PyUnusedLocal,PyRedeclaration,PyAbstractClass
    def test_lowercase_callable_attribute_must_not_have_different_signature(self):
        class ATool(dlb.ex.Tool):
            # noinspection PyUnusedLocal
            def x_y_z(self, s: str) -> int:  # ok, not in a base class
                return 0

            async def u_v(self):  # ok, not in a base class
                return 0

            a = dlb.ex.Tool.Input.RegularFile()

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
                u_v = dlb.ex.Tool.Input.RegularFile()
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
            x_y_z = dlb.ex.Tool.Input.RegularFile()

        t = dlb.ex.Tool()

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


class DependencyRuleOverrideTest(unittest.TestCase):

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_override_with_same(self):
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.Tool.Input.RegularFile()

        class BTool(ATool):
            source_file = dlb.ex.Tool.Input.RegularFile()

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_cannot_override_input_with_output(self):
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.Tool.Input.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_file = dlb.ex.Tool.Output.RegularFile()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_cannot_override_file_with_director(self):
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.Tool.Input.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_file = dlb.ex.Tool.Input.Directory()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_path_with_more_restrictive_path(self):
        import dlb.fs

        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.Tool.Input.RegularFile()

        class BTool(ATool):  # ok, cls is more restrictive
            source_file = dlb.ex.Tool.Input.RegularFile(cls=dlb.fs.NoSpacePath)

        with self.assertRaises(TypeError) as cm:
            class DTool(BTool):  # cls is less restrictive
                source_file = dlb.ex.Tool.Input.RegularFile()
        self.assertEqual(
            "attribute 'source_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_nonrequired_with_required(self):
        class ATool(dlb.ex.Tool):
            source_file = dlb.ex.Tool.Input.RegularFile(required=False)

        class BTool(ATool):  # ok, required=True is more restrictive than required=False
            source_file = dlb.ex.Tool.Input.RegularFile(required=True)

        with self.assertRaises(TypeError) as cm:
            class CTool(BTool):
                source_file = dlb.ex.Tool.Input.RegularFile(required=False)
        self.assertRegex(
            r"^attribute 'source_file' of base class may only be overridden by a "
            r"<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive$",
            str(cm.exception))

    # noinspection PyUnusedLocal,PyAbstractClass
    def test_can_only_override_with_similar_multiplicity(self):
        class ATool(dlb.ex.Tool):
            source_files = dlb.ex.Tool.Input.RegularFile[1:]()
            linked_file = dlb.ex.Tool.Output.RegularFile()

        with self.assertRaises(TypeError) as cm:
            class BTool(ATool):
                source_files = dlb.ex.Tool.Input.RegularFile()
        self.assertEqual(
            "attribute 'source_files' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Input.RegularFile'> at least as restrictive",
            str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            class CTool(ATool):
                linked_file = dlb.ex.Tool.Output.RegularFile[:]()
        self.assertEqual(
            "attribute 'linked_file' of base class may only be overridden by a "
            "<class 'dlb.ex.Tool.Output.RegularFile'> at least as restrictive",
            str(cm.exception))


class ToolReprTest(unittest.TestCase):

    # noinspection PyAbstractClass
    class ATool(dlb.ex.Tool):
        source_file = dlb.ex.Tool.Input.RegularFile()
        object_file = dlb.ex.Tool.Output.RegularFile()

    # noinspection PyAbstractClass
    class BTool(ATool):
        map_file = dlb.ex.Tool.Output.RegularFile(required=False)

    # noinspection PyAbstractClass
    class CTool(dlb.ex.Tool):
        source_file = dlb.ex.Tool.Input.RegularFile()

    class X:
        _X_y_Z = None
        a_b_c = 1

    # noinspection PyAbstractClass
    class DTool(CTool, X):
        object_file = dlb.ex.Tool.Output.RegularFile()

    def test_repr_name_reflects_recommended_module(self):
        self.assertEqual(repr(dlb.ex.Tool), "<class 'dlb.ex.Tool'>")

    # noinspection PyAbstractClass
    def test_shows_name_and_dependency_rules(self):
        self.assertEqual(repr(dlb.ex.Tool()), 'Tool()')

        t = ToolReprTest.BTool(source_file='x.cpp', object_file='x.cpp.o')
        text = "ToolReprTest.BTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'), map_file=None)"
        self.assertEqual(text, repr(t))

        class CTool(dlb.ex.Tool):
            pass

        self.assertEqual("ToolReprTest.test_shows_name_and_dependency_rules.<locals>.CTool()", repr(CTool()))

    def test_inherit_invalid_from_nontool(self):
        t = ToolReprTest.DTool(source_file='x.cpp', object_file='x.cpp.o')
        self.assertEqual("ToolReprTest.DTool(source_file=Path('x.cpp'), object_file=Path('x.cpp.o'))", repr(t))


class ToolDefinitionAmbiguityTest(testenv.TemporaryDirectoryTestCase):

    # noinspection PyAbstractClass
    def test_location_of_tools_are_correct(self):
        lineno = 382  # of this line

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
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname='u1/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname='u1/v.py')

            sys.path.insert(0, zip_file_path)
            # noinspection PyUnresolvedReferences
            import u1.v
            del sys.path[0]

        self.assertEqual(u1.v.A.definition_location, (os.path.realpath(zip_file_path), os.path.join('u1', 'v.py'), 2))

    def test_fails_for_zip_without_zip_suffix(self):
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
                    z.write(os.path.join(content_tmp_dir_path, '__init__.py'), arcname='u2/__init__.py')
                    z.write(os.path.join(content_tmp_dir_path, 'v.py'), arcname='u2/v.py')

            sys.path.insert(0, zip_file_path)
            # noinspection PyUnresolvedReferences
            with self.assertRaises(dlb.ex.DefinitionAmbiguityError) as cm:
                import u2.v
            del sys.path[0]

        msg = (
            "invalid tool definition: location of definition is unknown\n"
            "  | class: <class 'u2.v.A'>\n"
            "  | define the class in a regular file or in a zip archive ending in '.zip'\n"
            "  | note also the significance of upper and lower case of module search paths "
            "on case-insensitive filesystems"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_location_in_zip_archive_module_is_correct(self):
        with tempfile.TemporaryDirectory() as tmp_dir_path:
            with tempfile.TemporaryDirectory() as content_tmp_dir_path:
                with open(os.path.join(content_tmp_dir_path, 'u3.py'), 'w') as f:
                    f.write(
                        'import dlb.ex\n'
                        'class A(dlb.ex.Tool): pass'
                    )

                zip_file_path = os.path.join(tmp_dir_path, 'abc.zip')
                with zipfile.ZipFile(zip_file_path, 'w') as z:
                    z.write(os.path.join(content_tmp_dir_path, 'u3.py'), arcname='u3.py')

            sys.path.insert(0, zip_file_path)
            # noinspection PyUnresolvedReferences
            import u3
            del sys.path[0]

        self.assertEqual(u3.A.definition_location, (os.path.realpath(zip_file_path), 'u3.py', 2))

    # noinspection PyAbstractClass
    def test_definition_location_is_readonly(self):
        class A(dlb.ex.Tool):
            pass

        self.assertEqual(A.definition_location[0], os.path.realpath(__file__))

        with self.assertRaises(AttributeError):
            A.definition_location = 42

        self.assertEqual(A.definition_location[0], os.path.realpath(__file__))

    # noinspection PyUnusedLocal,PyPep8Naming
    def test_definition_fails_for_two_different_dynamic_definitions(self):
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

        B = f(False)
        with self.assertRaisesRegex(dlb.ex.DefinitionAmbiguityError, regex):
            C = f(True)

    def test_definition_fails_for_two_equal_dynamic_definitions(self):
        # noinspection PyUnusedLocal,PyAbstractClass
        def f(s):
            class A(dlb.ex.Tool):
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


class ToolInstanceConstructionTest(unittest.TestCase):

    # noinspection PyAbstractClass
    class ATool(dlb.ex.Tool):
        source_file = dlb.ex.Tool.Input.RegularFile()
        object_file = dlb.ex.Tool.Output.RegularFile()

    # noinspection PyAbstractClass
    class BTool(ATool):
        map_file = dlb.ex.Tool.Output.RegularFile(required=False)
        log_file = dlb.ex.Tool.Output.RegularFile(required=True, explicit=False)

    # noinspection PyAbstractClass
    class CTool(dlb.ex.Tool):
        envvar = dlb.ex.Tool.Input.EnvVar(name='n', restriction='.*', example='', required=False)

    # noinspection PyAbstractClass
    class DTool(BTool):
        include_directories = dlb.ex.Tool.Input.Directory[:](required=False)

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

        self.assertIsInstance(ToolInstanceConstructionTest.DTool.source_file, dlb.ex.Tool.Input)
        self.assertIsInstance(ToolInstanceConstructionTest.DTool.object_file, dlb.ex.Tool.Output)
        self.assertIsInstance(ToolInstanceConstructionTest.DTool.include_directories, dlb.ex.Tool.Input)
        self.assertIsInstance(ToolInstanceConstructionTest.DTool.map_file, dlb.ex.Tool.Output)

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
            "  | reason: iterable must be duplicate-free, but contains Path('i/') more than once"
        )
        self.assertEqual(msg, str(cm.exception))

    def test_must_not_have_argument_for_undeclared_dependency(self):
        msg = (
            "keyword argument does not name a dependency role of 'ToolInstanceConstructionTest.BTool': "
            "'temporary_file'\n"
            "  | dependency roles: 'source_file', 'log_file', 'object_file', 'map_file'"
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


class ToolInstanceFingerprintTest(unittest.TestCase):

    # noinspection PyAbstractClass
    class ATool(dlb.ex.Tool):
        source_file = dlb.ex.Tool.Input.RegularFile[:]()
        object_file = dlb.ex.Tool.Output.RegularFile(required=False)
        map_file = dlb.ex.Tool.Output.RegularFile(required=False)

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

    def test_is_20_byte(self):
        tool = ToolInstanceFingerprintTest.ATool(source_file=[], object_file='e.o')
        self.assertIsInstance(tool.fingerprint, bytes)
        self.assertEqual(20, len(tool.fingerprint))

    def test_is_readonly(self):
        tool = ToolInstanceFingerprintTest.ATool(source_file=[], object_file='e.o')
        with self.assertRaises(AttributeError):
            tool.fingerprint = b''


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
        os.mkdir('a')
        open(os.path.join('a/__init__.py'), 'x').close()
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

        with dlb.ex.Context():
            t = time.monotonic_ns()
            info1 = dlb.ex._tool.get_and_register_tool_info(w.E)
            dt1 = time.monotonic_ns() - t

            t = time.monotonic_ns()
            info2 = dlb.ex._tool.get_and_register_tool_info(w.E)
            dt2 = time.monotonic_ns() - t

        print(f'get_and_register_tool_info(): {dt1/1e3:.0f} us (first call), {dt2/1e3:.0f} us (second call)')

        self.assertIsInstance(info1.permanent_local_tool_id, bytes)
        self.assertGreater(len(info1.permanent_local_tool_id), 1)

        p1 = os.path.realpath(os.path.join(os.getcwd(), 'a', 'u.py'))
        p2 = os.path.realpath(os.path.join(os.getcwd(), 'w.py'))
        self.assertEqual(3, len(info1.definition_paths), info1.definition_paths)  # incl. _tool.py
        self.assertTrue(p1 in info1.definition_paths)
        self.assertTrue(p2 in info1.definition_paths)
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


class DependencyInheritanceTest(unittest.TestCase):

    def test_hierarchy_matches_nesting(self):
        self.assertTrue(issubclass(dlb.ex.Tool.Input, dlb.ex.Tool.Dependency))
        self.assertTrue(issubclass(dlb.ex.Tool.Input.RegularFile, dlb.ex.Tool.Input))
        self.assertTrue(issubclass(dlb.ex.Tool.Input.NonRegularFile, dlb.ex.Tool.Input))
        self.assertTrue(issubclass(dlb.ex.Tool.Input.Directory, dlb.ex.Tool.Input))
        self.assertTrue(issubclass(dlb.ex.Tool.Input.EnvVar, dlb.ex.Tool.Input))

        self.assertTrue(issubclass(dlb.ex.Tool.Output, dlb.ex.Tool.Dependency))
        self.assertTrue(issubclass(dlb.ex.Tool.Output.RegularFile, dlb.ex.Tool.Output))
        self.assertTrue(issubclass(dlb.ex.Tool.Output.NonRegularFile, dlb.ex.Tool.Output))
        self.assertTrue(issubclass(dlb.ex.Tool.Output.Directory, dlb.ex.Tool.Output))


class DependencyReprTest(unittest.TestCase):
    def test_name_matches_class(self):
        self.assertEqual(dlb.ex.Tool.__name__, 'Tool')
        self.assertEqual(dlb.ex.Tool.Dependency.__name__, 'Dependency')
        self.assertEqual(dlb.ex.Tool.Input.__name__, 'Input')
        self.assertEqual(dlb.ex.Tool.Output.__name__, 'Output')

    def test_repr_name_reflects_nesting(self):
        self.assertEqual(repr(dlb.ex.Tool.Dependency), "<class 'dlb.ex.Tool.Dependency'>")
        self.assertEqual(repr(dlb.ex.Tool.Input), "<class 'dlb.ex.Tool.Input'>")
        self.assertEqual(repr(dlb.ex.Tool.Input.RegularFile), "<class 'dlb.ex.Tool.Input.RegularFile'>")
        self.assertEqual(repr(dlb.ex.Tool.Output), "<class 'dlb.ex.Tool.Output'>")
        self.assertEqual(repr(dlb.ex.Tool.Output.RegularFile), "<class 'dlb.ex.Tool.Output.RegularFile'>")


class DependencyActionRegistrationTest(unittest.TestCase):

    # noinspection PyAbstractClass
    def test_fails_for_unregistered_dependency_class(self):
        class D(dlb.ex.Tool.Input.RegularFile):
            pass

        class T(dlb.ex.Tool):
            oho = D()

        regex = r"keyword names unregistered dependency class <class '.+'>: 'oho'"
        with self.assertRaisesRegex(dlb.ex.DependencyError, regex):
            T(oho='x')
