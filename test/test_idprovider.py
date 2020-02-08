import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here)))
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

import time
import dlb.ex
import dlb.ex.idprovider
import tools_for_test


class ToolRegistryTest(tools_for_test.TemporaryDirectoryTestCase):

    def test_path_for_tool_defined_out_managed_is_not_available(self):
        class A(dlb.ex.Tool):
            pass

        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            info = dlb.ex.idprovider.get_and_register_tool_info(A)

        self.assertGreater(len(info.permanent_local_id), 1)
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
        import w  # needs a name different from the already loaded modules
        del sys.path[0]

        os.mkdir('.dlbroot')
        with dlb.ex.Context():
            t = time.time()
            info1 = dlb.ex.idprovider.get_and_register_tool_info(w.E)
            dt1 = time.time() - t
            print(f'first time:  {dt1:6f} s')

            t = time.time()
            info2 = dlb.ex.idprovider.get_and_register_tool_info(w.E)
            dt2 = time.time() - t
            print(f'second time: {dt2:6f} s')

        self.assertIsInstance(info1.permanent_local_id, bytes)
        self.assertGreater(len(info1.permanent_local_id), 1)
        self.assertEqual(info1.definition_paths, set((dlb.fs.Path('a/u.py'), dlb.fs.Path('w.py'))))
        self.assertEqual(info1, info2)

    def test_definition_fails_in_import_with_relative_search_path(self):
        with open(os.path.join('z.py'), 'x') as f:
            f.write(
                'import dlb.ex\n'
                'class A(dlb.ex.Tool): pass\n'
            )

        sys.path.insert(0, '.')  # !
        with self.assertRaises(dlb.ex.tool.DefinitionAmbiguityError):
            import z  # needs a name different from the already loaded modules
        del sys.path[0]
