__all__ = ('TokensTemplate',)

import sys
import re
import collections
import collections.abc
import enum
import inspect
from . import util
assert sys.version_info >= (3, 6)


LITERAL_REGEX = re.compile(r'([^{}]|{{|}})+', re.DOTALL)

# only Python 2 identifiers (no non-ASCII characters)
ROOT_NAME_REGEX = re.compile(  # if x is matched by this, then x + '_' must be matched by PREFIXED_NAME_REGEX
    r'^((?P<prefix>[/<>^|;#$%&*=]+)|(?P<name>[A-Za-z][A-Za-z_0-9]*))\Z'
)

PREFIXED_NAME_REGEX = re.compile(
    r'(?P<prefix>[/<>^|;#$%&*=]*)'
    r'(?P<name>[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*)', re.DOTALL)
assert PREFIXED_NAME_REGEX.match('x.y.z').group() == 'x.y.z'
assert PREFIXED_NAME_REGEX.match('/#x.y').group('prefix') == '/#'

CONTAINER_DELIMS = collections.OrderedDict()  # sorted by length (descending)
CONTAINER_DELIMS['{:'] = '}'
CONTAINER_DELIMS['{'] = ':}'
CONTAINER_DELIMS['['] = ']'

UNORDERED_OPTS_REGEX = re.compile(r'[+!?]*')
OPTS_REGEX = re.compile(r'^\+?!?\??\Z')


def _node_path_to_str(path):
    return '.'.join([str(i) for i in path])


def _name_components_to_str(components):
    c = components[0]
    s = '.'.join(components[1:])
    m = PREFIXED_NAME_REGEX.match(c + '_')
    if s and not (m and m.group('prefix') == c):
        c += '.'
    return c + s


def _has_underscores(components):
    return any(c for c in components if c and c.startswith('_'))


def _first_prefixed_name(unprocessed):
    n = 0
    components = ()
    m = PREFIXED_NAME_REGEX.match(unprocessed)
    if m:
        prefix, name = m.group('prefix', 'name')
        n = m.end()
        components = name.split('.')
        if prefix:
            components = [prefix] + components
        components = tuple(components)
    return components, n


def _variable_message_format_dict(node_path, variable_spec, opt_postfix=''):
    postfix = opt_postfix
    if postfix:
        postfix = ': ' + postfix
    if node_path:
        node_path_prefix = 'node {0}: '.format(_node_path_to_str(node_path))
    else:
        node_path_prefix = ''
    return {
        'node_prefix': node_path_prefix,
        'var_name': repr(_name_components_to_str(variable_spec.var_name_components)),
        'type_name': repr(_name_components_to_str(variable_spec.type_name_components)),
        'postfix': postfix
    }


class _ScannedTemplateString:
    """
    A syntactically correct template string of a :class:`TokensTemplate`,
    consisting of string literals and variable specifications,
    Implements the scanning and syntax checking.
    """

    VariableSpecification = collections.namedtuple('VariableSpecification', [
        'var_name_components',
        'type_name_components',
        'type_opts',
        'container',
        'container_opts'
    ])

    def __init__(self, template_string, node_path, msg_prefix=''):
        """
        Splits *template_string* into the corresponding sequence of literals and variable specifications.
        A literal is a string to remain unchanged when a expansion is performed.
        A variable specifications defines its replacement by a single or multiple strings.

        The attribute ``parts`` of a :class:`_ScannedTemplateString` is a list of parts of *template_string*
        (strings for literals, :class:`VariableSpecification` for variable specifications).

        :rtype template_string: str
        :type node_path: tuple(int)
        :param node_path:
            path of the node *template_string* in its containing template group
            (child indices parent nodes, starting from root)
        :raise ValueError: if syntax error in *template_string*
        """
        self.parts = []

        unprocessed = template_string

        def node_msg():
            pos = len(template_string) - len(unprocessed)
            return (
                "{0}node {1} at position {2}"
            ).format(msg_prefix, _node_path_to_str(node_path), pos)

        while unprocessed:
            # leading literal
            m = LITERAL_REGEX.match(unprocessed)
            if m:
                # literal
                self.parts.append(m.group().replace('{{', '{').replace('}}', '}'))
                unprocessed = unprocessed[m.end():]
            elif unprocessed[0] == '{':
                # single '{' - start of variable specification
                # example: {tool.search_paths:[/dlb.fs.Path]?}

                unprocessed = unprocessed[1:]

                var_name_components, n = _first_prefixed_name(unprocessed)
                if not var_name_components:
                    raise ValueError("{0}: variable name expected".format(node_msg()))
                if _has_underscores(var_name_components):
                    raise ValueError("{0}: variable name components must not start with '_'"
                                     .format(node_msg()))
                unprocessed = unprocessed[n:]

                if unprocessed[:1] != ':':
                    raise ValueError("{0}: ':' expected after variable name".format(node_msg()))
                unprocessed = unprocessed[1:]

                container = None
                for container_opening in CONTAINER_DELIMS:
                    if unprocessed.startswith(container_opening):
                        container = container_opening
                        unprocessed = unprocessed[len(container_opening):]
                        break

                # "[" <type-name> <type-opts> "]" <container-opts>
                # "{" <type-name> <type-opts> ",]" <container-opts>
                # "{," <type-name> <type-opts> "]" <container-opts>

                type_name_components, n = _first_prefixed_name(unprocessed)
                if not type_name_components:
                    if container:
                        msg = "{0}: type name expected"
                    else:
                        msg = "{0}: type name or container opening expected"
                    raise ValueError(msg.format(node_msg()))
                if _has_underscores(type_name_components):
                    raise ValueError("{0}: type name components must not start with '_'"
                                     .format(node_msg()))
                unprocessed = unprocessed[n:]

                m = UNORDERED_OPTS_REGEX.match(unprocessed)
                type_opts = m.group()
                if not OPTS_REGEX.match(type_opts):
                    raise ValueError("{0}: invalid type options: {1}".format(node_msg(), repr(type_opts)))
                unprocessed = unprocessed[m.end():]

                if container:
                    container_closing = CONTAINER_DELIMS[container]
                    if not unprocessed.startswith(container_closing):
                        raise ValueError(
                            "{0}: type options or {1} expected".format(node_msg(), repr(container_closing)))
                    unprocessed = unprocessed[len(container_closing):]

                    m = UNORDERED_OPTS_REGEX.match(unprocessed)
                    container_opts = m.group()
                    if not OPTS_REGEX.match(container_opts):
                        raise ValueError("{0}: invalid container options: {1}".format(node_msg(), repr(type_opts)))
                    unprocessed = unprocessed[m.end():]
                else:
                    container_opts = None

                if unprocessed[:1] != '}':
                    raise ValueError("{0}: '}}' expected at end of variable specification".format(node_msg()))
                unprocessed = unprocessed[1:]

                assert var_name_components
                assert type_name_components
                var_spec = self.VariableSpecification(
                    var_name_components=var_name_components,
                    type_name_components=type_name_components,
                    type_opts=type_opts,
                    container=container,
                    container_opts=container_opts
                )
                self.parts.append(var_spec)
            else:
                raise ValueError("{0}: unbalanced '}}'".format(node_msg()))


class TokensTemplate:
    @enum.unique
    class LookupScope(enum.Enum):
        LOCAL = 0  # locals() of the caller
        GLOBAL = 1  # globals() and builtins() of the caller
        KNOWN = 2  # any name known in the callers' scope (for read acess)

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)

        msg_tmpl = (
            "{0}(): each node must be a string or tuple: "
            "node at (argument) index {{0}} is not"
        ).format(self.__class__.__qualname__)
        self._root_group = self._scan_tree(args, (), msg_tmpl)
        # The root scanned template group.
        # It is the root of an ordered tree whose leafs are _ScannedTemplateString and whose non-leaf nodes are lists
        # of child nodes.
        #
        # The structure remains intact (this allows references to source token in exception messages).
        # Example:
        #
        #   [
        #     'a{z:str}b',
        #     (),
        #     (
        #       'a',
        #       ('c{d:e}',  'b'),
        #       '',
        #     )
        #   ]
        #
        # becomes
        #
        #   [
        #     _ScannedTemplateString('a{z:str}b'),
        #     [],
        #     [
        #        _ScannedTemplateString('a'),
        #        [
        #           _ScannedTemplateString('c{d:e}')
        #           _ScannedTemplateString('b')
        #        ]
        #        _ScannedTemplateString(''),
        #     ]
        #   ]

        self._root_or_scope_by_name = {}
        # keys: names of roots (str)
        # values: root objects or instances of cls.LookupScope or None

        self._protected_root_ids = set()
        # id(v) if v defined a root with value v should be prevented

        self._type_by_name_components = None
        # if not None:
        #     keys: tuples of type name components
        #     values: t with instance(t, type) == True

    @staticmethod
    def escape_literal(literal):
        return literal.replace('{', '{{').replace('}', '}}')

    def protect(self, *args):
        arg_ids = set(id(arg) for arg in args)  # non-hashable objects possible
        if id(None) in arg_ids:
            raise ValueError("None cannot be protected")
        self._protected_root_ids |= arg_ids
        return self

    def define(self, *args, **kwargs):
        if args:
            if len(args) > 1:
                raise TypeError('define() takes at most 1 positional argument')
            if not (isinstance(args[0], collections.abc.Mapping) and
                    all(isinstance(k, str) for k in args[0])):
                raise TypeError('positional argument must be a mapping whose keys are strings')
            self._add_roots(args[0])
        self._add_roots(kwargs)
        return self

    def lookup_types(self, frames_up=0):
        msg = "'frames_up' must be non-negative integer'"
        if not isinstance(frames_up, int):
            raise TypeError(msg)
        if frames_up < 0:
            raise ValueError(msg)
        frames = inspect.stack(0)[frames_up + 1:]  # no context lines
        self._type_by_name_components = {}
        self._lookup_types_in_tree(self._root_group, (), frames)
        return self

    def expand(self, frames_up=0):
        msg = "'frames_up' must be non-negative integer'"
        if not isinstance(frames_up, int):
            raise TypeError(msg)
        if frames_up < 0:
            raise ValueError(msg)
        if self._type_by_name_components is None:
            self.lookup_types(frames_up)
        frames = inspect.stack(0)[frames_up + 1:]  # no context lines

        value_by_name_components = {}
        # keys: (name_component, container), where name_component is a tuple of value name components
        # values:
        #   if container = '[': tuple of values or None
        #   if container = '{' or '{:': tuple of tuples (k, v) or None
        #   else: single value or None

        return self._expand_group(self._root_group, (), frames, value_by_name_components)

    def _expand_group(self, child_nodes, node_path, frames, value_by_name_components):
        assert isinstance(child_nodes, list)

        expanded_child_nodes = []  # list(list(str))

        common_multiplicity = 1
        index = None

        for i, child_node in enumerate(child_nodes):
            child_node_path = node_path + (i,)
            if isinstance(child_node, _ScannedTemplateString):
                et, is_list_valued = self._expand_string(child_node, child_node_path, frames, value_by_name_components)
                if is_list_valued:
                    multiplicity = len(et)
                    if index is None:
                        common_multiplicity = multiplicity
                        index = i
                    elif multiplicity != common_multiplicity:
                        if index is not None and multiplicity != common_multiplicity:
                            raise ValueError((
                                "incompatible lengths of expanded token lists: "
                                "node {0} -> {1} tokens, node {2} -> {3} tokens"
                            ).format(_node_path_to_str(node_path + (index,)), common_multiplicity,
                                     _node_path_to_str(node_path + (i,)), multiplicity))
                        common_multiplicity = multiplicity
                        index = i
            else:
                et = self._expand_group(child_node, child_node_path, frames, value_by_name_components)
                if et:
                    et = [et]
            if et:
                # [...a, [], ...c]  ->  [...a, ...c]
                expanded_child_nodes.append(et)

        for i, expanded_child_node in enumerate(expanded_child_nodes):
            if len(expanded_child_node) != common_multiplicity:
                expanded_child_nodes[i] = expanded_child_node * common_multiplicity

        expanded_tokens = []
        for et in zip(*expanded_child_nodes):
            for e in et:
                if isinstance(e, list):
                    expanded_tokens.extend(e)
                else:
                    expanded_tokens.append(e)

        return expanded_tokens  # list(str)

    def _expand_string(self, template_string, node_path, frames, value_by_name_components):
        multi_values = []

        common_multiplicity = 1
        variable_spec = None

        for i, part in enumerate(template_string.parts):
            if isinstance(part, str):
                multi_value = part
            else:
                assert isinstance(part, _ScannedTemplateString.VariableSpecification)
                multi_value = self._expand_variable(part, node_path, frames,
                                                    value_by_name_components)
                if isinstance(multi_value, list):
                    multiplicity = len(multi_value)
                    if variable_spec is None:
                        variable_spec = part
                    elif multiplicity != common_multiplicity:
                        var_name1 = _name_components_to_str(variable_spec.var_name_components)
                        var_name2 = _name_components_to_str(part.var_name_components)
                        raise ValueError((
                            "node {0}: incompatible lengths of expanded token lists: "
                            "{1} -> {2} tokens, {3} -> {4} tokens"
                        ).format(_node_path_to_str(node_path),
                                 repr(var_name1), common_multiplicity,
                                 repr(var_name2), multiplicity))
                    common_multiplicity = multiplicity
            if multi_value is not None:
                multi_values.append(multi_value)

        # multi_values: list(str | list(str))

        # expand multi values (in template string)
        #
        # examples:
        #
        #   x = ['a', 'b'], y = [1, 2], z = ')'
        #   '({x:[str]}{y:[int]}{z:str}' -> ['(a1)', '(b2)']
        #
        #   x = []
        #   '<({x:[str]}>' -> []

        for i, multi_value in enumerate(multi_values):
            if not isinstance(multi_value, list):
                multi_values[i] = [multi_value] * common_multiplicity
        expanded_tokens = list(''.join(mv) for mv in zip(*multi_values))

        is_list_valued = variable_spec is not None  # at least one container variable specification?
        return expanded_tokens, is_list_valued  # list(str)

    def _expand_variable(self, variable_spec, node_path, frames, value_by_name_components):
        """
        Expands a variable according to its specification *variable_spec* and caches its values
        in *value_by_name_components*.

        :type variable_spec: :class:`_ScannedTemplateString.VariableSpecification`
        :type node_path: list(int)
        :param frames: list(tuple(frame, ...))
        :type value_by_name_components: dict((tuple(str), None | str): None | tuple())
        :param value_by_name_components: cache for looked-up variable values
        :rtype: None | str | list(str)
        :return: None (to be ignore) or expanded value (if no container) or expanded values (if container)

        :raise NameError: if root of *variable_spec*\ ``.var_name_components`` is not defined
        :raise LookupError: if *variable_spec*\ ``.var_name_components`` is not found in its root
        :raise ValueError: if a value of *variable_spec* is None or empty
        :raise TypeError: if a value of *variable_spec* cannot be converted into its declared type

        Precondition: *variable_spec*\ ``.type_name_components`` in ``self._type_by_name_components``
        """
        typ = self._type_by_name_components[variable_spec.type_name_components]

        var_name_key = (
            variable_spec.var_name_components,
            {
                None: None,
                '[': '[',
                '{': '{',
                '{:': '{'
            }[variable_spec.container])

        if var_name_key in value_by_name_components:
            value = value_by_name_components[var_name_key]
        else:
            value = self._lookup_name(variable_spec.var_name_components, node_path, frames)
            if variable_spec.container:
                value = self._check_and_coerce_container(node_path, variable_spec, value)
            value_by_name_components[var_name_key] = value

        expanded_values = None
        if variable_spec.container:
            # values is tuple
            if value is not None:
                expanded_values = []
                if variable_spec.container == '{':
                    value = (k for k, v in value)
                elif variable_spec.container == '{:':
                    value = (v for k, v in value)
                for v in value:
                    v = self._expand_variable_value(variable_spec, node_path, v, typ)
                    if v is not None:
                        expanded_values.append(v)
            # interpret container options (how to handle None and empty container)
            none_because_empty = False
            if expanded_values is not None and '+' in variable_spec.container_opts:
                # treat 'empty value' as None
                if not expanded_values:
                    expanded_values = None
                    none_because_empty = True
            if expanded_values is None and '!' in variable_spec.container_opts:
                # replace None by list()
                expanded_values = []
            if expanded_values is None and '?' not in variable_spec.container_opts:
                if none_because_empty:
                    msg_tmpl = \
                        "{node_prefix}value of variable {var_name} (with container option '+', without '?') is empty"
                else:
                    msg_tmpl = "{node_prefix}value of variable {var_name} (without container option '?') is None"
                raise ValueError(msg_tmpl.format(**_variable_message_format_dict(node_path, variable_spec)))
        else:
            expanded_values = self._expand_variable_value(variable_spec, node_path, value, typ)

        return expanded_values

    def _expand_variable_value(self, variable_spec, node_path, value, typ):
        if value is not None and not isinstance(value, typ):
            # value is known -> coerce to declared type
            try:
                value = typ(value)
            except Exception as e:
                raise TypeError((
                    "{node_prefix}cannot construct object of declared type {type_name} "
                    "from value {value} of variable {var_name}{postfix}"
                ).format(value=repr(value), **_variable_message_format_dict(node_path, variable_spec, str(e))))

        # interpret type options (how to handle None and empty value)
        none_because_empty = False
        if value is not None and '+' in variable_spec.type_opts:
            # treat 'empty value' as None
            try:
                if not value:  # calls value.__bool__()
                    value = None
                    none_because_empty = True
            except Exception as e:
                raise TypeError((
                    "{node_prefix}cannot convert object of declared type {type_name} "
                    "of variable {var_name} to 'bool'{postfix}"
                ).format(**_variable_message_format_dict(node_path, variable_spec, str(e))))
        if value is None and '!' in variable_spec.type_opts:
            # replace None by typ()
            try:
                value = typ()
            except Exception as e:
                raise TypeError((
                    "{node_prefix}cannot construct default object of type {type_name} "
                    "for variable {var_name}{postfix}"
                ).format(**_variable_message_format_dict(node_path, variable_spec, str(e))))
        none_is_error = '?' not in variable_spec.type_opts

        if value is not None:
            # value is of declared type -> convert to str
            try:
                value = str(value)
                if not isinstance(value, str):
                    raise TypeError
            except Exception as e:
                raise TypeError((
                    "{node_prefix}cannot convert value of variable {var_name} "
                    "(coerced to declared type {type_name}) to 'str'{postfix}"
                ).format(**_variable_message_format_dict(node_path, variable_spec, str(e))))

        if value is None and none_is_error:
            if none_because_empty:
                msg_tmpl = "{node_prefix}value of variable {var_name} (with type option '+', without '?') is empty"
            else:
                msg_tmpl = "{node_prefix}value of variable {var_name} (without type option '?') is None"
            raise ValueError(msg_tmpl.format(**_variable_message_format_dict(node_path, variable_spec)))

        return value

    @classmethod
    def _check_and_coerce_container(cls, node_path, variable_spec, values):
        if values is not None:
            expected_descr = None
            try:
                if variable_spec.container == '[':
                    expected_descr = "sequence-like"
                    # https://docs.python.org/3/glossary.html#term-iterable
                    if isinstance(values, str) or not all(hasattr(values, m) for m in ('__len__', '__getitem__')):
                        raise TypeError
                    values = tuple(v for v in values)
                elif variable_spec.container in ('{', '{:'):
                    expected_descr = "mapping-like"
                    if not all(hasattr(values, m) for m in ('__len__', '__getitem__', 'items')):
                        raise TypeError
                    values = tuple((k, v) for k, v in values.items())
                else:
                    raise TypeError
            except Exception as e:
                raise TypeError((
                    "{node_prefix}variable {var_name} must be {expected_descr}; "
                    "{type} is not{postfix}"
                ).format(expected_descr=expected_descr, type=type(values),
                         **_variable_message_format_dict(node_path, variable_spec, str(e))))
        return values

    def _lookup_types_in_tree(self, root, node_path, frames):
        assert isinstance(root, list)
        for i, child_node in enumerate(root):
            child_node_path = node_path + (i,)
            if isinstance(child_node, _ScannedTemplateString):
                for part in child_node.parts:
                    if isinstance(part, _ScannedTemplateString.VariableSpecification):
                        self._lookup_type(part, child_node_path, frames)
            else:
                self._lookup_types_in_tree(child_node, child_node_path, frames)

    def _lookup_type(self, variable_spec, node_path, frames):
        if variable_spec.type_name_components not in self._type_by_name_components:
            obj = self._lookup_name(variable_spec.type_name_components, node_path, frames)
            if obj is not None and not isinstance(obj, type):
                type_name = _name_components_to_str(variable_spec.type_name_components)
                raise TypeError('node {0}: type name {1} refers to a non-type object'
                                .format(_node_path_to_str(node_path), repr(type_name)))
            self._type_by_name_components[variable_spec.type_name_components] = obj

    def _lookup_name(self, name_components, node_path, frames):
        """
        Lookup a name *name_components* in the defined roots.

        :type name_components: list(str)
        :param node_path: list(int)
        :param frames: list(tuple(frame, ...))
        :return: root object (may be None)

        :raise NameError: if root in *name_components* is not defined
        :raise LookupError: if *name_components* is not found in its root
        """
        root_name = name_components[0]
        if root_name not in self._root_or_scope_by_name:
            raise NameError('node {0}: root {1} not defined'
                            .format(_node_path_to_str(node_path), repr(root_name)))
        root_or_scope = self._root_or_scope_by_name.get(root_name, None)
        nonroot_name_components = name_components[1:]
        found_count = None
        try:
            if isinstance(root_or_scope, self.LookupScope):
                root, found = self._lookup_in_frames(root_or_scope, nonroot_name_components[0], frames)
                nonroot_name_components = nonroot_name_components[1:]
                if not found:
                    raise AttributeError
                found_count = 2
            else:
                root = root_or_scope
                found_count = 1
            obj = root  # may be None
            for c in nonroot_name_components:
                obj = getattr(obj, c)  # may be None
                found_count += 1
        except AttributeError:
            msg = 'node {0}: {1} is not defined'\
                .format(_node_path_to_str(node_path),
                        repr(_name_components_to_str(name_components)))
            if found_count is not None:
                msg += ' ({0} has no attribute {1})'\
                    .format(repr(_name_components_to_str(name_components[:found_count])),
                            repr(name_components[found_count]))
            raise LookupError(msg)
        return obj

    @classmethod
    def _lookup_in_frames(cls, scope, root_name, frames):
        # https://docs.python.org/3/library/inspect.html#the-interpreter-stack
        found = False
        root = None

        def lookup_in(d):
            if root_name in d:
                return d[root_name], True
            else:
                return None, False

        if scope is cls.LookupScope.KNOWN:
            for i in range(len(frames)):
                try:
                    frame = frames[i][0]
                    root, found = lookup_in(frame.f_locals)
                    if not found:
                        root, found = lookup_in(frame.f_globals)
                    if not found:
                        root, found = lookup_in(frame.f_builtins)
                    if found:
                        break
                finally:
                    del frame
        else:
            try:
                frame = frames[0][0]
                if scope is cls.LookupScope.LOCAL:
                    root, found = lookup_in(frame.f_locals)
                else:  # cls.LookupScope.GLOBAL:
                    root, found = lookup_in(frame.f_globals)
                    if not found:
                        root, found = lookup_in(frame.f_builtins)
            finally:
                del frame

        return root, found  # root may be None

    def _add_roots(self, root_or_scope_by_name):
        for k, v in root_or_scope_by_name.items():
            if not ROOT_NAME_REGEX.match(k):
                raise ValueError('invalid as root name: {0}'.format(repr(k)))
            if k in self._root_or_scope_by_name:
                raise ValueError('root {0} is already defined'.format(repr(k)))
            if id(v) in self._protected_root_ids:
                raise ValueError('value of root {0} is protected: {1}'.format(repr(k), repr(v)))
        self._root_or_scope_by_name.update(root_or_scope_by_name)

    @classmethod
    def _scan_tree(cls, root, node_path, msg_tmpl):
        scanned_root = []
        for i, group in enumerate(root):
            child_node_path = node_path + (i,)
            if isinstance(group, str):
                scanned = _ScannedTemplateString(group, child_node_path, '{0}(): '.format(cls.__qualname__))
                scanned_root.append(scanned)
            elif isinstance(group, tuple):
                # note: restriction to non-mutable sequence makes self-containing sequences impossible
                scanned_root.append(cls._scan_tree(group, child_node_path, msg_tmpl))
            else:
                raise TypeError(msg_tmpl.format(_node_path_to_str(child_node_path)))
        return scanned_root


for exported_name in __all__:
    util.remove_last_component_from_dotted_module_name(vars()[exported_name])
del exported_name
