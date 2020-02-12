import sys
import os.path
here = os.path.dirname(__file__) or os.curdir
sys.path.insert(0, os.path.abspath(os.path.join(here, '../src')))

from dlb.ex import TokensTemplate
import collections
import unittest


class TestModule(unittest.TestCase):

    def test_import(self):
        import dlb.ex.tmpl
        self.assertEqual({'TokensTemplate'}, set(dlb.ex.tmpl.__all__))
        self.assertTrue('TokensTemplate' in dir(dlb.ex))


class TestSyntax(unittest.TestCase):

    def test_invalid_type(self):
        with self.assertRaises(TypeError):
            TokensTemplate(None)

        with self.assertRaises(TypeError) as cm:
            TokensTemplate('abc', 4, None)
        self.assertEqual("TokensTemplate(): each node must be a string or tuple: "
                         "node at (argument) index 1 is not",
                         str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            TokensTemplate('a', ('b', ('c', ('d', 4))))
        self.assertEqual("TokensTemplate(): each node must be a string or tuple: "
                         "node at (argument) index 1.1.1.1 is not",
                         str(cm.exception))

    def test_recursive_list(self):
        l = ['a', 'b']
        # noinspection PyTypeChecker
        l.append(l)
        l2 = ['c', l]
        with self.assertRaises(TypeError) as cm:
            TokensTemplate(l2)
        self.assertEqual("TokensTemplate(): each node must be a string or tuple: node at (argument) index 0 is not",
                         str(cm.exception))

    def test_literal_with_braces(self):
        TokensTemplate('x{{y', '{{{{c\n}}}}')

    def test_nonmatching_braces(self):
        with self.assertRaises(ValueError) as cm:
            TokensTemplate('a}b')
        self.assertEqual("TokensTemplate(): node 0 at position 1: unbalanced '}'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{{a{b')
        self.assertEqual("TokensTemplate(): node 0 at position 5: ':' expected after variable name",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{{a{b:')
        self.assertEqual("TokensTemplate(): node 0 at position 6: "
                         "type name or container opening expected",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{{a{b:str')
        self.assertEqual("TokensTemplate(): node 0 at position 9: "
                         "'}' expected at end of variable specification",
                         str(cm.exception))

    def test_type_options(self):
        TokensTemplate('{b:str+!?}')

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:str+?!?}')
        self.assertEqual("TokensTemplate(): node 0 at position 6: "
                         "invalid type options: '+?!?'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:str?!+}')
        self.assertEqual("TokensTemplate(): node 0 at position 6: "
                         "invalid type options: '?!+'",
                         str(cm.exception))

    def test_underscore_in_name(self):
        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{_b:str}')
        self.assertEqual("TokensTemplate(): node 0 at position 1: "
                         "variable name components must not start with '_'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b.c._d:str}')
        self.assertEqual("TokensTemplate(): node 0 at position 1: "
                         "variable name components must not start with '_'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b.c.d:_str}')
        self.assertEqual("TokensTemplate(): node 0 at position 7: "
                         "type name components must not start with '_'",
                         str(cm.exception))

    def test_sequence(self):
        TokensTemplate('{b:[str]}')
        TokensTemplate('{b:[str+]?}')

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:[str')
        self.assertEqual("TokensTemplate(): node 0 at position 7: "
                         "type options or ']' expected",
                         str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:[str}')
        self.assertEqual("TokensTemplate(): node 0 at position 7: "
                         "type options or ']' expected",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:str]')
        self.assertEqual("TokensTemplate(): node 0 at position 6: "
                         "'}' expected at end of variable specification",
                         str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:[]}')
        self.assertEqual("TokensTemplate(): node 0 at position 4: "
                         "type name expected",
                         str(cm.exception))

    def test_mapping(self):
        TokensTemplate('{b:{:str+?}!}')
        TokensTemplate('{b:{str+?:}}')

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:{str}')
        self.assertEqual("TokensTemplate(): node 0 at position 7: "
                         "type options or ':}' expected",
                         str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:{str')
        self.assertEqual("TokensTemplate(): node 0 at position 7: "
                         "type options or ':}' expected",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:{str}')
        self.assertEqual("TokensTemplate(): node 0 at position 7: "
                         "type options or ':}' expected",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:{}')
        self.assertEqual("TokensTemplate(): node 0 at position 4: "
                         "type name expected",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:{:}')
        self.assertEqual("TokensTemplate(): node 0 at position 5: "
                         "type name expected",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:{str:str}')
        self.assertEqual("TokensTemplate(): node 0 at position 7: "
                         "type options or ':}' expected",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            TokensTemplate('{b:{str:str:}')
        self.assertEqual("TokensTemplate(): node 0 at position 7: "
                         "type options or ':}' expected",
                         str(cm.exception))


class TestNameLookup(unittest.TestCase):

    def test_define(self):
        tmpl = TokensTemplate()
        self.assertEqual({}, tmpl._root_or_scope_by_name)
        self.assertIs(tmpl, tmpl.define())

        with self.assertRaises(TypeError) as cm:
            tmpl.define(1)
        self.assertEqual("positional argument must be a mapping whose keys are strings",
                         str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            tmpl.define({}, {})
        self.assertEqual("define() takes at most 1 positional argument",
                         str(cm.exception))

        with self.assertRaises(TypeError) as cm:
            tmpl.define({1: 2})
        self.assertEqual("positional argument must be a mapping whose keys are strings",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            tmpl.define({'': 2})
        self.assertEqual("invalid as root name: ''",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            tmpl.define({'a.b': 2})
        self.assertEqual("invalid as root name: 'a.b'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            tmpl.define({'_a': 2})
        self.assertEqual("invalid as root name: '_a'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            tmpl.define({'/a': 2})
        self.assertEqual("invalid as root name: '/a'",
                         str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            tmpl.define({'a': 2}, a=2)
        self.assertEqual("root 'a' is already defined",
                         str(cm.exception))

        tmpl.define(x=1, y=2).define({'/#^': tmpl.LookupScope.GLOBAL})
        with self.assertRaises(ValueError) as cm:
            tmpl.define(y=2)
        self.assertEqual("root 'y' is already defined",
                         str(cm.exception))

        tmpl.define(z=None)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(z=2)
        self.assertEqual("root 'z' is already defined",
                         str(cm.exception))

    def test_protect(self):
        tmpl = TokensTemplate()
        tmpl.protect('1', 4, 2.0, int, tmpl.LookupScope.KNOWN).protect(5)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(z=tmpl.LookupScope.KNOWN)
        self.assertEqual("value of root 'z' is protected: <LookupScope.KNOWN: 2>",
                         str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            tmpl.protect(None)
        self.assertEqual("None cannot be protected",
                         str(cm.exception))

    def test_lookup_types(self):
        # noinspection PyUnusedLocal
        u = int
        tmpl = TokensTemplate('{x:str}', '{y:/u}')
        tmpl.define({'/': tmpl.LookupScope.KNOWN}, str=str)
        self.assertIsNone(tmpl._type_by_name_components)
        self.assertIs(tmpl, tmpl.lookup_types())
        self.assertEqual({('str',): str, ('/', 'u'): int}, tmpl._type_by_name_components)

        # noinspection PyUnusedLocal
        class A:

            v = float
            u = list

            class B:
                # globals and builtins found:
                tmpl = TokensTemplate(
                    '{a:/TokensTemplate}',
                    '{b:/str}').define({'/': TokensTemplate.LookupScope.GLOBAL})
                tmpl.lookup_types()
                self.assertEqual({('/', 'TokensTemplate'): TokensTemplate, ('/', 'str'): str},
                                 tmpl._type_by_name_components)

                # non-global not found as global:
                tmpl = TokensTemplate('{a:/v}').define({'/': TokensTemplate.LookupScope.GLOBAL})
                with self.assertRaises(LookupError) as cm:
                    tmpl.lookup_types()
                self.assertEqual("node 0: '/v' is not defined",
                                 str(cm.exception))

                # local found:
                z = tuple
                tmpl = TokensTemplate('{a:>z}').define({'>': TokensTemplate.LookupScope.LOCAL})
                tmpl.lookup_types()
                self.assertEqual({('>', 'z'): tuple}, tmpl._type_by_name_components)

                with self.assertRaises(LookupError) as cm:
                    tmpl.lookup_types(1)
                self.assertEqual("node 0: '>z' is not defined",
                                 str(cm.exception))

                tmpl = TokensTemplate('{a:>v}').define({'>': TokensTemplate.LookupScope.LOCAL})
                tmpl.lookup_types(1)
                self.assertEqual({('>', 'v'): float}, tmpl._type_by_name_components)

                # non-local not found:
                tmpl = TokensTemplate('{a:>v}').define({'>': TokensTemplate.LookupScope.LOCAL})
                with self.assertRaises(LookupError) as cm:
                    tmpl.lookup_types()
                self.assertEqual("node 0: '>v' is not defined",
                                 str(cm.exception))

                # known found
                tmpl = TokensTemplate('{a:#z}', '{b:#v}', '{c:#u}{d:#TokensTemplate}', '{e:#str}')
                tmpl.define({'#': TokensTemplate.LookupScope.KNOWN})
                tmpl.lookup_types(0)
                self.assertEqual(
                    {
                        ('#', 'z'): tuple,
                        ('#', 'v'): float,
                        ('#', 'u'): list,
                        ('#', 'TokensTemplate'): TokensTemplate,
                        ('#', 'str'): str
                    },
                    tmpl._type_by_name_components)

        tmpl = TokensTemplate('{x:y}').define(y=1)
        with self.assertRaises(TypeError) as cm:
            tmpl.lookup_types()
        self.assertEqual("node 0: type name 'y' refers to a non-type object",
                         str(cm.exception))

        tmpl = TokensTemplate('{a:/A.B.x.y}').define({'/': TokensTemplate.LookupScope.LOCAL})
        with self.assertRaises(LookupError) as cm:
            tmpl.lookup_types()
        self.assertEqual("node 0: '/A.B.x.y' is not defined ('/A.B' has no attribute 'x')",
                         str(cm.exception))

        tmpl = TokensTemplate('{a:A.B.x.y}').define(A=int)
        with self.assertRaises(LookupError) as cm:
            tmpl.lookup_types()
        self.assertEqual("node 0: 'A.B.x.y' is not defined ('A' has no attribute 'B')",
                         str(cm.exception))


class TestExpansion(unittest.TestCase):

    def test_escape(self):
        self.assertEqual('', TokensTemplate.escape_literal(''))
        self.assertEqual('x\n y', TokensTemplate.escape_literal('x\n y'))
        self.assertEqual(['x\n y}{{'],
                         TokensTemplate(TokensTemplate.escape_literal('x\n y}{{')).expand())

    def test_expand_normal(self):
        self.assertEqual([], TokensTemplate().expand())
        self.assertEqual(['xx{]\n ', 'y}z'],
                         TokensTemplate('xx{{]\n ', 'y}}z').expand())

        tmpl = TokensTemplate('x{a:str}{b:int}y', '{b:int}').define(str=str, int=int)
        self.assertEqual(['xA3y', '3'],
                         tmpl.define(a='A', b=3).expand())

        tmpl = TokensTemplate('{a:[str]}{b:str}').define(str=str)
        self.assertEqual(['12'], tmpl.define(a=['1'], b='2').expand())

        tmpl = TokensTemplate('x{a:str}{b:[int]}y').define(str=str, int=int)
        self.assertEqual(['xA1y', 'xA2y', 'xA3y'],
                         tmpl.define(a='A', b=range(1, 4)).expand())

        tmpl = TokensTemplate('<{a:[str]}={b:[str]}>').define(str=str)
        self.assertEqual(['<A=1>', '<B=2>', '<C=3>'],
                         tmpl.define(a=['A', 'B', 'C'], b=range(1, 4)).expand())

        tmpl = TokensTemplate('<{a:{str:}}={a:{:str}}>').define(str=str)
        a = collections.OrderedDict()
        a['A'] = 1
        a['B'] = 2
        a['C'] = 3
        self.assertEqual(['<A=1>', '<B=2>', '<C=3>'], tmpl.define(a=a).expand())

        tmpl = TokensTemplate('_{a:[str]}').define(str=str)
        self.assertEqual([], tmpl.define(a=[]).expand())
        tmpl = TokensTemplate('_{a:[str?]}').define(str=str)
        self.assertEqual(['_A', '_B', '_C'], tmpl.define(a=['A', None, 'B', 'C']).expand())
        tmpl = TokensTemplate('_{a:[str!]}').define(str=str)
        self.assertEqual(['_A', '_', '_B', '_C'], tmpl.define(a=['A', None, 'B', 'C']).expand())

        tmpl = TokensTemplate('_{a:[str]!}').define(str=str)
        self.assertEqual([], tmpl.define(a=None).expand())
        tmpl = TokensTemplate('_{a:[str]?}').define(str=str)
        self.assertEqual(['_'], tmpl.define(a=None).expand())

        tmpl = TokensTemplate('_{x:int?}').define(int=int)
        self.assertEqual(['_'], tmpl.define(x=None).expand())
        tmpl = TokensTemplate('_{x:int!}').define(int=int)
        self.assertEqual(['_0'], tmpl.define(x=None).expand())
        tmpl = TokensTemplate('_{x:int+?}').define(int=int)
        self.assertEqual(['_'], tmpl.define(x=None).expand())

        tmpl = TokensTemplate('_{x:int+?}').define(int=int)
        self.assertEqual(['_'], tmpl.define(x=0).expand())

    def test_expand_check(self):

        with self.assertRaises(NameError) as cm:
            TokensTemplate('{x:str}').expand()
        self.assertEqual("node 0: root 'str' not defined",
                         str(cm.exception))

        with self.assertRaises(NameError) as cm:
            TokensTemplate('{x:str}').define(str=str).expand()
        self.assertEqual("node 0: root 'x' not defined",
                         str(cm.exception))

        tmpl = TokensTemplate('{x:str}').define(str=str)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(x=None).expand()
        self.assertEqual("node 0: value of variable 'x' (without type option '?') is None",
                         str(cm.exception))

        tmpl = TokensTemplate('{x:int+}').define(int=int)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(x=0).expand()
        self.assertEqual("node 0: value of variable 'x' (with type option '+', without '?') is empty",
                         str(cm.exception))

        class A:
            def __init__(self, x, y):
                del x, y

        tmpl = TokensTemplate('{a:A}').define(A=A)
        with self.assertRaises(TypeError) as cm:
            tmpl.define(a=1).expand()
        self.assertRegex(str(cm.exception),
                         r"^node 0: cannot construct object of declared type 'A' from value 1 of variable 'a': .*")

        class B:
            def __init__(self, x):
                del x

            def __str__(self):
                pass

        tmpl = TokensTemplate('{b:B}').define(B=B)
        with self.assertRaises(TypeError) as cm:
            tmpl.define(b=1).expand()
        self.assertRegex(str(cm.exception),
                         r"^node 0: cannot convert value of variable 'b' "
                         r"\(coerced to declared type 'B'\) to 'str': .*")

        tmpl = TokensTemplate('a', '{b:B?}', 'c').define(B=B)
        self.assertEqual(['a', 'c'], tmpl.define(b=None).expand())

        tmpl = TokensTemplate('<{b:B?}{b2:[str]}>').define(B=B, str=str)
        self.assertEqual(['<2>', '<3>'], tmpl.define(b=None, b2=['2', '3']).expand())

        tmpl = TokensTemplate('a', '<{b:B?}{b2:[str]}>', 'c').define(B=B, str=str)
        self.assertEqual([], tmpl.define(b=None, b2=[]).expand())

        tmpl = TokensTemplate('a', '<{b1:[str]}{b2:[str]}>', 'c').define(B=B, str=str)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(b1=[], b2=['2', '3']).expand()
        self.assertEqual("node 1: incompatible lengths of expanded token lists: "
                         "'b1' -> 0 tokens, 'b2' -> 2 tokens",
                         str(cm.exception))

        tmpl = TokensTemplate('a', '<{b1:[str]}{b2:[str]}>', 'c').define(B=B, str=str)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(b1=['1'], b2=['2', '3']).expand()
        self.assertEqual("node 1: incompatible lengths of expanded token lists: "
                         "'b1' -> 1 tokens, 'b2' -> 2 tokens",
                         str(cm.exception))

        tmpl = TokensTemplate('<{b1:[str]+?}{b2:[str]}>').define(B=B, str=str)
        self.assertEqual(['<2>', '<3>'], tmpl.define(b1=[], b2=['2', '3']).expand())

        class C:
            def __bool__(self):
                pass

        tmpl = TokensTemplate('{c:C+}').define(C=C)
        with self.assertRaises(TypeError) as cm:
            tmpl.define(c=C()).expand()
        self.assertRegex(str(cm.exception),
                         r"^node 0: cannot convert object of declared type 'C' of variable 'c' to 'bool': .*")

        class D:
            def __init__(self, x):
                del x

        tmpl = TokensTemplate('{d:D!}').define(D=D)
        with self.assertRaises(TypeError) as cm:
            tmpl.define(d=None).expand()
        self.assertRegex(str(cm.exception),
                         r"^node 0: cannot construct default object of type 'D' for variable 'd': .*")

        tmpl = TokensTemplate('{d:[D]}').define(D=D)
        with self.assertRaises(TypeError) as cm:
            tmpl.define(d=D(1)).expand()
        self.assertRegex(str(cm.exception),
                         r"^node 0: variable 'd' must be sequence-like; <class .*> is not")

        tmpl = TokensTemplate('{d:{D:}}').define(D=D)
        with self.assertRaises(TypeError) as cm:
            tmpl.define(d=D(1)).expand()
        self.assertRegex(str(cm.exception),
                         r"^node 0: variable 'd' must be mapping-like; <class .*> is not")
        tmpl = TokensTemplate('{d:{:D}}').define(D=D)
        with self.assertRaises(TypeError) as cm:
            tmpl.define(d=D(1)).expand()
        self.assertRegex(str(cm.exception),
                         r"^node 0: variable 'd' must be mapping-like; <class .*> is not")

        tmpl = TokensTemplate('{d:[int]}').define(int=int)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(d=None).expand()
        self.assertEqual("node 0: value of variable 'd' (without container option '?') is None",
                         str(cm.exception))
        tmpl = TokensTemplate('{d:[int]?}').define(int=int)
        self.assertEqual([], tmpl.define(d=None).expand())

        tmpl = TokensTemplate('{d:[int+?]+}').define(int=int)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(d=[0, 0, 0]).expand()
        self.assertEqual("node 0: value of variable 'd' (with container option '+', without '?') is empty",
                         str(cm.exception))
        tmpl = TokensTemplate('{d:[int+?]+?}').define(int=int)
        self.assertEqual([], tmpl.define(d=[0, 0, 0]).expand())

    def test_token_groups(self):
        tmpl = TokensTemplate('-I', '{a:[int]}').define(int=int)
        self.assertEqual(['-I', '1', '-I', '2', '-I', '3'], tmpl.define(a=[1, 2, 3]).expand())

        tmpl = TokensTemplate(('{a:[int]}',), ('{b:[int]}',)).define(int=int)
        self.assertEqual(['1', '2', '1', '2', '3'], tmpl.define(a=[1, 2], b=[1, 2, 3]).expand())

        tmpl = TokensTemplate('{a:[int]}', ('b', 'c'), '{a:[int]}').define(int=int)
        self.assertEqual(['1', 'b', 'c', '1', '2', 'b', 'c', '2'], tmpl.define(a=[1, 2]).expand())

        tmpl = TokensTemplate('a', '<{b:int?}{b2:[str]}>', 'c').define(str=str, int=int)
        self.assertEqual(['a', '<2>', 'c', 'a', '<3>', 'c'], tmpl.define(b=None, b2=['2', '3']).expand())

        tmpl = TokensTemplate('a', '<{b1:[str]+?}{b2:[str]}>', 'c').define(str=str)
        self.assertEqual(['a', '<2>', 'c', 'a', '<3>', 'c'], tmpl.define(b1=[], b2=['2', '3']).expand())

        tmpl = TokensTemplate('x{a:str}{b:[int]}y', '{b:[str]}').define(str=str, int=int)
        self.assertEqual(['xA1y', '1', 'xA2y', '2', 'xA3y', '3'],
                         tmpl.define(a='A', b=range(1, 4)).expand())

        tmpl = TokensTemplate('{a:int}', '{b:[int]}').define(int=int)
        self.assertEqual([], tmpl.define(a=1, b=[]).expand())

        tmpl = TokensTemplate(('0', ('{a:int}', '3'), ()), '{b:[int]}').define(int=int)
        self.assertEqual([], tmpl.define(a=1, b=[]).expand())
        tmpl = TokensTemplate(('0', ('{a:int}', '3'), ()), '{b:[int]}').define(int=int)
        self.assertEqual(['0', '1', '3', '8', '0', '1', '3', '9'], tmpl.define(a=1, b=[8, 9]).expand())
        tmpl = TokensTemplate(('0', ('{a:[int]}', '3'), ()), '{b:[int]}').define(int=int)
        self.assertEqual(['0', '1', '3', '2', '3', '8', '0', '1', '3', '2', '3', '9'],
                         tmpl.define(a=[1, 2], b=[8, 9]).expand())

        tmpl = TokensTemplate('{a:[int]}', '{b:int?}', '{c:[int]}').define(int=int)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(a=[1, 2], b=None, c=[1, 2, 3]).expand()
        self.assertEqual("incompatible lengths of expanded token lists: node 0 -> 2 tokens, node 2 -> 3 tokens",
                         str(cm.exception))

        tmpl = TokensTemplate('{a:[int]}', '{b:[int]}').define(int=int)
        with self.assertRaises(ValueError) as cm:
            tmpl.define(a=[1], b=[1, 2, 3]).expand()
        self.assertEqual("incompatible lengths of expanded token lists: node 0 -> 1 tokens, node 1 -> 3 tokens",
                         str(cm.exception))

    def test_single_lookup(self):
        tmpl = TokensTemplate('{a:str}',
                              ('{a:[str]}',),
                              ('{a:{str:}}',),
                              ('{a:{:str}}',)).define(str=str)

        a = collections.OrderedDict()
        a[1] = 'A'
        a[2] = 'B'

        self.assertEqual([
            "OrderedDict([(1, 'A'), (2, 'B')])",
            '1', '2',
            '1', '2',
            'A', 'B'
        ], tmpl.define(a=a).expand())

        class A:
            def __init__(self, items):
                self._items = items
                self.getitem_count = 0
                self.items_count = 0

            def __len__(self):
                return len(self._items)

            def __getitem__(self, i):
                self.getitem_count += 1
                return self._items[i][0]

            def __repr__(self):
                return 'A({0})'.format(self._items)

            def items(self):
                self.items_count += 1
                return self._items

        a = A([(1, 'A'), (2, 'B')])
        tmpl = TokensTemplate('{a:str}',
                              ('{a:[str]}',),
                              ('{a:{str:}}',),
                              ('{a:{:str}}',)
                              ).define(str=str)
        self.assertEqual([
            "A([(1, 'A'), (2, 'B')])",
            '1', '2',
            '1', '2',
            'A', 'B'
        ], tmpl.define(a=a).expand())

        self.assertEqual(3, a.getitem_count)
        self.assertEqual(1, a.items_count)


class ReprTest(unittest.TestCase):

    def test_repr_name_reflects_recommended_module(self):
        self.assertEqual(repr(TokensTemplate), "<class 'dlb.ex.TokensTemplate'>")

