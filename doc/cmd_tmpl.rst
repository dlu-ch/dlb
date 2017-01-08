:mod:`dlb.cmd.tmpl` --- Tokens Templates
========================================

String-token based replacement engine which provides simple type checking (with ``isinstance()``)
and support for iteration (and repetition) over sequences and mappings.
It's primary intended use is command line compilation from file list etc.

.. _tmpl-expansion-rules:

Syntax and Expansion Rules
--------------------------

A template is an ordered tree whose leafs are *template strings* and whose non-leaf
nodes are *template groups*.
The root of a template is always a template group.

When constructing a :class:`TokensTemplate`, every template strings is represented by a string
and every template group is represented by a tuple of its (direct) children.

Example:

    ::

        tmpl = TokensTemplate(
            '{tool.cplusplus_compiler_path:dlb.fs.Path.Native}',
            '-x', 'c++',
            (
                '-I', '{tool.include_paths:[dlb.fs.Path.Native+]+?}'
            ),
            (
                '-D', '{tool.macros:{Tool.MacroDefinitionName+?:}}={tool.macros:{:Tool.MacroDefinitionReplacement!}+?}'
            ),
            '{tool.optional_argument:str?}',
            '--',
            (
                '{tool.source_file_paths:[dlb.fs.Path.Native]}',
            )
        )

    describes the following template tree:

        .. digraph:: template_example1_unexpanded

           graph [fontname=Helvetica, fontsize=10];
           node [fontname=Helvetica, fontsize=10, shape=rect, style=filled, fillcolor=white];
           edge [fontname=Helvetica, fontsize=10];

           root[shape=circle, label=""];
           root -> "'{tool.cplusplus_compiler_path:dlb.fs.Path.Native}'";
           root -> "'-x'";
           root -> "'c++'";

           root -> group1;
           group1[shape=circle, label=""];
           group1 -> "'-I'";
           group1 -> "'{tool.include_paths:[dlb.fs.Path.Native+]+?}'";

           root -> group2;

           group2[shape=circle, label=""];
           group2 -> "'-D'";
           group2 -> "'{tool.macros:{Tool.MacroDefinitionName+?:}}={tool.macros:{:Tool.MacroDefinitionReplacement!}+?}'";

           root -> "'{tool.optional_argument:str?}'"
           root -> "'--'";

           root -> group3
           group3[shape=circle, label=""];
           group3 -> "'{tool.source_file_paths:[dlb.fs.Path.Native]}'";

The expansion of the template is the expansion of its root.

The expansion process can be pictured as expanding all the leaf-nodes and "collapsing" all the
non-leaf nodes, bottom-up, until only the root is left.


Expansion of a template string (leaf node)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The (successful) expansion of a leaf node results in either a list of tokens or ``None``.

First, the template string is partitioned into the largest possible *literals*
(e.g. ``'in this example string braces ({{) are escaped by doubling'``) and *variable specification*
(e.g. ``'{tool.names:[str+]}'``).

Each part is then expanded separately:

* A (valid) literal part is expanded to exactly one value (the string it represents) by
  replacing all ``'{{'`` by ``'{'`` and all ``'}}'`` by ``'}'``.

  A literal part is syntactically valid iff it has the following form:

  .. productionlist:: tokenstmpl
     literal: ('{{' | '}}' | `nonbrace_character`)*
     nonbrace_character: any Unicode character except '{' and '}'

* A (valid) variable specification is replaced by its value or is omitted.

  Each variable specification consists of a variable name and a type specification.
  The type specification describes the type requirements of the variable's values.
  Example:

      ``'{a.b:[dlb.fs.Path.Native]?}'``

  describes a variable with name ``'a.b'`` of type 'optional list of ``dlb.fs.Path.Native`` objects'.

  Variable names (``'a.b'`` in the example) and type names (``dlb.fs.Path.Native`` in the example)
  are looked-up in root objects defined with :meth:`TokensTemplate.define()`.
  The type specification states whether a variable specification is a
  :ref:`non-container variable specification <tmpl-expansion-varspec-noncontainer>`,
  a :ref:`sequence-like variable specification <tmpl-expansion-varspec-sequence>` or
  a :ref:`mapping-like variable specification <tmpl-expansion-varspec-mapping>`

  A variable specification is syntactically valid iff it has the following form:

  .. productionlist:: tokenstmpl
     varspect: `noncont_varspect` | `sequence_varspect` | `mapping_varspect`


The parts are called *non-valued*, *single-valued* and *list-valued* according to their expansion.

After expanding each part of the template string, all single-valued and list-valued parts
are combined into a single token list as follows:
Let *n* be the length of the value list of all list-valued parts
(if there is no such value, a :exc:`ValueError` is raised).
For each *i* from 0 to *n* - 1, a combined token *t* is built by concatenating the value of the
single-valued parts and the *i*-th element of the values of the list-valued parts, preserving
their order.
The list of the *t* is the expanded token list of the template string.

Example (assuming ``x = ['a', 'b', 'c']`` and ``y = [1, 2, 3]``)::

   '<{x:[str]}={y:[int]}>'  ->   ['<a=1>', '<b=2>', '<c=3>']

A template string is called *list-valued* if it contains at least one list-valued part.


.. _tmpl-expansion-varspec-noncontainer:

Non-container variable specification
""""""""""""""""""""""""""""""""""""

A variable specification of the form

   .. productionlist:: tokenstmpl
      noncont_varspect: '{' `variable_name` ':' `type_name` `type_options` '}'

describes a *non-container variable*.

   .. productionlist:: tokenstmpl
      variable_name: `prefixed_dottet_name`
      type_name: `prefixed_dottet_name`
      prefixed_dottet_name: [`name_prefix`] `dottet_name`
      dottet_name: `name` ('.' `name`)
      name: `name_firstchar` `name_char`*
      name_firstchar: 'A' .. 'Z' | 'a' .. 'z' | '_'
      name_char: `name_firstchar` | '0' .. '9'
      name_prefix: `name_prefix_char` (`name_prefix_char`)*
      name_prefix_char: '/' | '\' | '<' | '>' | '^' | '|' | ';' | '#' | '$' | '%' | '&' | '*' | '='
      type_options: ['+'] ['!'] ['?']

*variable_name* and *type_name* are looked-up in root objects defined
with :meth:`TokensTemplate.define()`, resulting in the value ``v``
and the type ``T`` of the variable, respectively.

Every *variable_name* of a :token:`noncont_varspect` and every *type_name* are looked-up exactly
once for the entire template. So, ``v`` and ``T`` are guaranteed to be the same for every occurrence
of their name in a :token:`noncont_varspect`.

If ``v`` is not ``None`` it is coerced into the type ``T``:
Iff then ``not isinstance(v, T)`` is ``True``), ``v`` is replaced by ``T(v)``.

Then the *type_options* are evaluated from left to right
(one character at a time):

   +---------+-----------------------------------------------------------+
   | Option  | Effect                                                    |
   +=========+===========================================================+
   | ``'+'`` | iff ``not v`` is ``True``,                                |
   |         | replace ``v`` by ``None``                                 |
   +---------+-----------------------------------------------------------+
   | ``'!'`` | iff ``v`` is ``None``, replace ``v`` by ``T()``           |
   +---------+-----------------------------------------------------------+
   | ``'?'`` | do not raise :exc:`ValueError` if ``v`` is ``None``       |
   +---------+-----------------------------------------------------------+

Without ``'?'`` :exc:`ValueError` is raised if ``v`` is ``None``.

The variable specification is expanded to ``None`` if ``v`` is ``None``
and to ``str(v)`` otherwise.

Examples::

    '{i:int}'   with i = None   ->  raise ValueError
    '{i:int?}'  with i = None   ->  None
    '{i:int!}'  with i = None   ->  '0' (= str(int()))
    '{i:int+?}' with i = 0      ->  None
    '{i:int}'   with i = 2      ->  '2'
    '{i:int}'   with i = 1.4    ->  '1' (= str(int(1.4)))


.. _tmpl-expansion-varspec-sequence:

Sequence-like variable specification
""""""""""""""""""""""""""""""""""""

A variable specification of the form

   .. productionlist:: tokenstmpl
      sequence_varspect: '{' `variable_name` ':[' `type_name` `type_options` ']' `container_options` '}'

describes a *sequence-like container variable*.

   .. productionlist:: tokenstmpl
      container_options: type_options

*variable_name* and *type_name* are looked-up in root objects defined
with :meth:`TokensTemplate.define()`, resulting in the value ``vs``
and the type ``T`` of the variable, respectively.

Every *variable_name* of a :token:`sequence_varspect` and every *type_name* are looked-up exactly
once for the entire template. So, ``vs`` and ``T`` are guaranteed to be the same for every occurrence
of their name in a :token:`sequence_varspect`.

If ``vs`` is not ``None`` it is coerced into a sequence of ``T``\ s:
it is replaced by ``[v for k in vs]`` where each ``k`` is coerced into ``T`` and
*type_options* are applied as for the variable value of a
:ref:`non-container variable specification <tmpl-expansion-varspec-noncontainer>`.
Elements which are ``None`` are removed.

.. note::

   Although the order of element in the resulting ``vs`` is undefined if the variable value was
   of an unorderered type, it is guaranteed to be the same for all occurrences of *variable_name*
   in a :token:`sequence_varspect`.

After this the *container_options* are evaluated from left to right
(one character at a time):

   +---------+-----------------------------------------------------------+
   | Option  | Effect                                                    |
   +=========+===========================================================+
   | ``'+'`` | iff ``not vs`` is ``True``,                               |
   |         | replace ``vs`` by ``None``                                |
   +---------+-----------------------------------------------------------+
   | ``'!'`` | iff ``vs`` is ``None``, replace ``vs`` by ``[]``          |
   +---------+-----------------------------------------------------------+
   | ``'?'`` | do not raise :exc:`ValueError` if ``vs`` is ``None``      |
   +---------+-----------------------------------------------------------+

Without ``'?'`` :exc:`ValueError` is raised if ``vs`` is ``None``.

The variable specification is expanded to ``None`` if ``vs`` is ``None`` and to 0 or more
values ``[str(v) for v in vs]`` otherwise.

Examples::

    '{s:[int]}'    with s = None               ->  raise ValueError
    '{s:[int]?}'   with s = None               ->  None
    '{s:[int]!}'   with s = None               ->  []
    '{s:[int+?]?}' with s = [0, 1.4, None, 2]  ->  ['1', '2']


.. _tmpl-expansion-varspec-mapping:

Mapping-like variable specification
"""""""""""""""""""""""""""""""""""

A variable specification of the form

   .. productionlist:: tokenstmpl
      mapping_varspect: `mapping_key_varspect` | `mapping_value_varspect`
      mapping_key_varspect: '{' `variable_name` ':{' `type_name` `type_options` ':}' `container_options` '}'
      mapping_value_varspect: '{' `variable_name` ':{:' `type_name` `type_options` '}' `container_options` '}'

describes a *mapping-like container variable* in the *key form* or *value form* ,
respectively (note the position of the second ':').

Every *variable_name* of a :token:`mapping_varspect` and every *type_name* are looked-up exactly
once for the entire template. So, ``vs`` and ``T`` are guaranteed to be the same for every occurrence
of their name in a :token:`mapping_varspect`.

If the value ``vs`` of the variable is not ``None`` it is coerced into a mapping,
whose keys are ``T``s:
it is replaced by ``[(k, v) for k, v in vs.items()]``
and then each ``k`` or ``v`` (for key form or value form, respectively) is coerced into ``T`` and
*type_options* are applied as for the value of a
:ref:`non-container variable specification <tmpl-expansion-varspec-noncontainer>`.
Elements whose ``k`` or ``v`` (for key form or value form, respectively) is ``None`` are removed.

.. note::

   Although the order of element in the resulting ``vs`` is undefined if the variable value was
   of an unorderered type, it is guaranteed to be the same for all occurrences of *variable_name*
   in a :token:`mapping_varspect`).

After this the *container_options* are evaluated from left to right
(one character at a time):

   +---------+-----------------------------------------------------------+
   | Option  | Effect                                                    |
   +=========+===========================================================+
   | ``'+'`` | iff ``not vs`` is ``True``,                               |
   |         | replace ``vs`` by ``None``                                |
   +---------+-----------------------------------------------------------+
   | ``'!'`` | iff ``vs`` is ``None``, replace ``vs`` by ``[]``          |
   +---------+-----------------------------------------------------------+
   | ``'?'`` | do not raise :exc:`ValueError` if ``vs`` is ``None``      |
   +---------+-----------------------------------------------------------+

Without ``'?'`` :exc:`ValueError` is raised if ``vs`` is ``None``.

The variable specification is expanded to ``None`` if ``vs`` is ``None`` and to 0 or more
values ``[str(k) for k, v in vs]`` or ``[str(v) for k, v in vs]``
(for key form or value form, respectively) otherwise.

Examples::

    '{m:{int:}}'   with m = None                                 ->  raise ValueError
    '{m:{:int}?}'  with m = None                                 ->  None
    '{m:{int:}!}'  with m = None                                 ->  []
    '{m:{:int+?}}' with m = {'A': 0, None: 1.4, 2: None, '': 2}  ->  ['1', '2']  # in any order


Expansion of a template group (non-leaf node)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The (successful) expansion of a non-leaf node results in a list of tokens.

All (direct) children are expanded, each to a token list or ``None``.
Non-list-valued template strings expanding to ``None`` and template groups expanding to empty
tokens lists are ignored.

Let *n* be the length of the expanded token list of all list-valued template strings.
(if there is no such value, a :exc:`ValueError` is raised).
For each *i* from 0 to *n* - 1, a combined token list *l* is built by concatenating the token of
the single-valued template strings, all the tokens of the (child) template groups and the *i*-th
of the tokens of the list-valued template strings, preserving their order.

These *l* are then all concatenated, resulting in the final expanded token list.

Example:

    ::

        tmpl = TokensTemplate(
            '{tool.cplusplus_compiler_path:dlb.fs.Path.Native}',
            '-x', 'c++',
            (
                '-I', '{tool.include_paths:[dlb.fs.Path.Native+]+?}'
            ),
            (
                '-D', '{tool.macros:{Tool.MacroDefinitionName+?:}}={tool.macros:{:Tool.MacroDefinitionReplacement!}+?}'
            ),
            '{tool.optional_argument:str?}',
            '--',
            (
                '{tool.source_file_paths:[dlb.fs.Path.Native]}',
            )
        )

        ... = tmpl.define(...).expand()

    Unexpanded template:

        .. digraph:: template_example1_unexpanded

           graph [fontname=Helvetica, fontsize=10];
           node [fontname=Helvetica, fontsize=10, shape=rect, style=filled, fillcolor=white];
           edge [fontname=Helvetica, fontsize=10];

           root[shape=circle, label=""];
           root -> "'{tool.cplusplus_compiler_path:dlb.fs.Path.Native}'";
           root -> "'-x'";
           root -> "'c++'";

           root -> group1;
           group1[shape=circle, label=""];
           group1 -> "'-I'";
           group1 -> "'{tool.include_paths:[dlb.fs.Path.Native+]+?}'";

           root -> group2;

           group2[shape=circle, label=""];
           group2 -> "'-D'";
           group2 -> "'{tool.macros:{Tool.MacroDefinitionName+?:}}={tool.macros:{:Tool.MacroDefinitionReplacement!}+?}'";

           root -> "'{tool.optional_argument:str?}'"
           root -> "'--'";

           root -> group3
           group3[shape=circle, label=""];
           group3 -> "'{tool.source_file_paths:[dlb.fs.RelativePath.Native]}'";


    After expansion of all leaf-nodes,
    assuming ``tool.include_paths`` = ``[]``, ``tool.macros`` = ``{'a': 1, 'b': 'a'}``,
    ``tool.source_file_paths`` = ``['./a/b', './u']``, ``tool.optional_argument`` = ``None``:

        .. digraph:: template_example1_expanded1

           graph [fontname=Helvetica, fontsize=10];
           node [fontname=Helvetica, fontsize=10, shape=rect, style=filled, fillcolor=white];
           edge [fontname=Helvetica, fontsize=10];

           root[shape=circle, label=""];
           "'/usr/bin/g++'"[fillcolor=lightblue];
           root -> "'/usr/bin/g++'";
           "'-x'"[fillcolor=lightblue];
           root -> "'-x'";
           "'c++'"[fillcolor=lightblue];
           root -> "'c++'";

           root -> group1;
           group1[shape=circle, label=""];
           "'-I'"[fillcolor=lightblue];
           group1 -> "'-I'";
           "[]"[fillcolor=lightyellow];
           group1 -> "[]";

           root -> group2;

           group2[shape=circle, label=""];
           "'-D'"[fillcolor=lightblue];
           group2 -> "'-D'";
           "['a=1', 'b=a']"[fillcolor=lightyellow];
           group2 -> "['a=1', 'b=a']";

           "None"[fillcolor=coral2]
           root -> "None"
           "'--'"[fillcolor=lightblue];
           root -> "'--'";

           root -> group3
           group3[shape=circle, label=""];
           "['./a/b', './u']"[fillcolor=lightyellow];
           group3 -> "['./a/b', './u']";


    After expansion of all second-level nodes:

        .. digraph:: template_example1_expanded2

           graph [fontname=Helvetica, fontsize=10];
           node [fontname=Helvetica, fontsize=10, shape=rect, style=filled, fillcolor=white];
           edge [fontname=Helvetica, fontsize=10];

           root[shape=circle, label=""];
           "'/usr/bin/g++'"[fillcolor=lightblue];
           root -> "'/usr/bin/g++'";
           "'-x'"[fillcolor=lightblue];
           root -> "'-x'";
           "'c++'"[fillcolor=lightblue];
           root -> "'c++'";

           root -> group1;
           group1[shape=egg, fillcolor=lightgray, label="[]"];

           root -> group2;
           group2[shape=egg, fillcolor=lightgray, label="['-D', 'a=1', '-D', 'b=a']"];

           "None"[fillcolor=coral2]
           root -> "None"
           "'--'"[fillcolor=lightblue];
           root -> "'--'";

           root -> group3
           group3[shape=egg, fillcolor=lightgray, label="['./a/b', './u']"];

    After complete expansion:

        .. digraph:: template_example1_expanded3

           graph [fontname=Helvetica, fontsize=10];
           node [fontname=Helvetica, fontsize=10, shape=rect, style=filled, fillcolor=lightblue];
           edge [fontname=Helvetica, fontsize=10];

           root[shape=egg, fillcolor=lightgray,
               label="['/usr/bin/g++', '-x', 'c++', '-D', 'a=1', '-D', 'b=a', '--', './a/b', './u']"];


Module Contents
---------------

.. class:: TokensTemplate

    A :class:`TokensTemplate` represents a template - containing string literals and typed variable specifications -
    which can later be expanded into a sequence of strings (tokens).
    Sequence and mappings types are supported; they expand to 0 or more string token.
    Once constructed, the template cannot be changed.

    The template is an ordered tree whose leafs are *template strings*.
    It is described by template strings and (arbitrarily deep nested) tuples of template strings
    (forming the non-leaf nodes of the tree). The non-leaf nodes are called *template groups*.

    Template groups are only significant if sequence- or mapping-like variables are used.
    They allow the isolation of variables of different length and the building of "repetition groups".

    Variable types and values are looked-up in roots.
    Roots can be defined or protected between construction and :meth:`expand()`.
    Once protected, a root cannot be defined.
    Once defined, a root value cannot be changed.

    Types can be looked-up in a different scope than values by explicitly calling :meth:`lookup_types()`.

    See :ref:`tmpl-expansion-rules` for details.

   .. method:: TokensTemplate(*args, **kwargs)

      :type args: list(str | tuple)
      :param args:
         Each positional argument is a template group (a tree).
         The non-leaf nodes are described by tuples of their children (template groups or template strings).

   .. staticmethod:: escape_literal(literal)

      Returns the token template string, which represents the literal *literal*.

      For every string ``s``, the following is ``True``::

          TokensTemplate(TokensTemplate.escape_literal(s)).expand() == [s]

      :type literal: str
      :param literal: string to escape
      :rtype: str
      :return: escaped ``literal``

   .. method:: protect([objects-to-protect])

      Add all arguments (which must be hashable) to the set of protected roots.

      :return: ``self``
      :raise ValueError: if any positional argument is ``None``

   .. method:: define([roots])

      Defines additional roots for the lookup of type and variable names.

      The prefix or first component in a :class:`TokensTemplate` type or variable name is the root name.
      Examples:

      - The root in ``x.y.z`` is ``x`` (``y.z`` is looked-up in ``x``).
      - The root in ``/Path`` is ``/`` (``Path`` is looked-up in ``/``).

      The keys of keyword arguments define names of roots, their values the corresponding root objects or
      :class:`LookupScope` instances.

      At most one positional argument is accepted which must be a :class:`collections.abc.Mapping}`, mapping
      additional root names (which must be strings) to root objects or :class:`LookupScope` instances.

      :class:`LookupScope` instances are special: a name in the corresponding root is looked up in the frame
      of the caller of :meth:`lookup_types()` and :meth:`expand()`, depending on the scope defined by the instance.

      Valid root names are :token:`root_name`\ s:

      .. productionlist:: tokenstmpl
         root_name: `name` | `name_prefix`

      :return: ``self``
      :raise ValueError: if a root name is invalid
      :raise ValueError: if a root is already defined or protected

   .. method:: lookup_types(frames_up=0)

      Looks up the types of all variable specifications (replaces previously looked-up types, if available).

      :type frames_up: int
      :param frames_up:
         The frame to be considered as local. Frames below (more local) are never searched during lookup.
         0 means the frame of the caller of this method, 1 means its enclosing frame etc.
         Must be non-negative.
      :return: ``self``

      :raise NameError: if the root of the type name in a variable specification is not defined
      :raise LookupError: if the type name in a variable specification is not found in its root
      :raise TypeError: if the type name in a variable specification refers to an non-type object in its root

   .. method:: expand(frames_up=0)

      Expands this template to a list of tokens.
      Variable specifications are replaced.
      Each variable is evaluated at most once (exactly once, if successful).

      :type frames_up: int
      :param frames_up:
         The frame to be considered as local. Frames below (more local) are never searched during lookup.
         0 means the frame of the caller of this method, 1 means its enclosing frame etc.
         Must be non-negative.
      :rtype: list(str)
      :return: expanded tokens

      :raise NameError: if the root of the variable or type name in a variable specification is not defined
      :raise LookupError: if the variable or type name in a variable specification is not found in its root
      :raise TypeError: if the type name in a variable specification refers to an non-type object in its root
      :raise ValueError: if the value of a variable violates the requirements declared in a variable specification
