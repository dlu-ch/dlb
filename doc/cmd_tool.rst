:mod:`dlb.cmd.tool` --- Dependency-Aware Command-Line Tools
===========================================================
.. module:: dlb.cmd
   :synopsis: Dependency-Aware Command-Line Tools

This module provides classes to represent tools to be executed during the build process.

*Tools* are the workhorses of every build tools.

In dlb, tools are classes derived from :class:`dlb.cmd.Tool`.
Tool instances are immutable and hashable;
tools are customized by inheritance and defining class attributes.


Tool Objects
------------

.. class:: dlb.cmd.Tool

   A tool declares its *dependency roles* (e.g. ``map_file_dependency``) and *execution parameters*
   (e.g. ``DO_INCLUDE_DEBUG_INFO``, ``PAPER_FORMAT``) as class attributes.

   Every tool instance assigns concrete *dependencies* for the tool's dependency roles
   (e.g. a filesystem path ``'./out/hello.map'`` for a dependency role ``map_file_dependency``),
   while the execution parameters are the same of all instances of the some tool.

   Dependency roles are instances of subclasses of :class:`dlb.cmd.Tool.DependencyRole`.

   A new tool can be defined by inheriting from one or more other tools.
   When overriding a dependency roles, its overriding value must be of the same type as the overridden value
   and it must be at least as restrictive (e.g. if required dependency must not be overridden by a non-required one).
   When overriding an execution parameters, its overriding value must be of the same type as the overridden value.

   Example::

      class Compiler(dlb.cmd.Tool):
         WARNINGS = ('all',)
         source_file = dlb.cmd.Tool.Input.RegularFile()
         object_file = dlb.cmd.Tool.Output.RegularFile()

      class Linker(dlb.cmd.Tool):
         object_files = dlb.cmd.Tool.Input.RegularFile[1:]()
         linked_file = dlb.cmd.Tool.Output.RegularFile()
         map_file = dlb.cmd.Tool.Output.RegularFile(is_required=False)

      compiler = Compiler(source_file='main.cpp', object_file='main.cpp.o')
      linker = Linker(object_files=[compiler.object_file], linked_file='main')


   At construction of a tool, the dependencies given as keyword arguments to the constructor are validated by the
   tool's dependency roles and made accessible (for reading only) as an attribute with the name of the corresponding
   dependency role and a type determined by the dependency role
   (e.g. :class:`dlb.fs.Path` for :class:`dlb.cmd.Tool.Input.RegularFile`)::

      >>> Compiler.object_file  # dependency role
      <dlb.cmd.tool.Tool.Input.RegularFile object at ...>

      >>> compiler.object_file  # dependency
      Path('main.cpp.o')

   .. method:: run_in_context()


Dependency Role Classes
-----------------------

Dependency roles of tools (subclasses of :class:`Tool`) are instances of subclasses of
:class:`dlb.cmd.Tool.DependencyRole`.

.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.cmd.Tool.Input" -> "dlb.cmd.Tool.DependencyRole";
       "dlb.cmd.Tool.Intermediate" -> "dlb.cmd.Tool.DependencyRole";
       "dlb.cmd.Tool.Output" -> "dlb.cmd.Tool.DependencyRole";
   }

They are classified according to their meaning to the tool:

.. class:: dlb.cmd.Tool.DependencyRole

   Base class of all dependency roles.

.. class:: dlb.cmd.Tool.Input

   A :class:`dlb.cmd.Tool.DependencyRole` which describes an input dependency of a tool.

   The tool is not executed if such a dependency (e.g. a file) does not exist.
   The tool must be rerun if it (e.g. the content of a file) has changed compared to the state before it
   was executed.

.. class:: dlb.cmd.Tool.Intermediate

   A :class:`dlb.cmd.Tool.DependencyRole` which describes an intermediate dependency of a tool.

   Such a dependency (e.g. a directory for caching) is expected not to be accessed while the tool
   is executed.

.. class:: dlb.cmd.Tool.Output

   A :class:`dlb.cmd.Tool.DependencyRole` which describes an output dependency of a tool.

   The dDependency (e.g. a file) is removed before the tool is not executed.
   After the execution of the tool it must exist.

These classes are used for structure only; the have no meaningful attribute or methods.
Concrete dependencies can only be assigned to *concrete dependency rules*.
The according classes are inner classes of :class:`dlb.cmd.Tool.Input`, :class:`dlb.cmd.Tool.Intermediate` and
:class:`dlb.cmd.Tool.Output` and derived from these.
Example: :class:`dlb.cmd.Tool.Output.Directory` is a concrete output dependency rule
(a subclass of :class:`dlb.cmd.Tool.Output`).


Concrete Dependency Role Classes and Objects
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Their objects are used to declare dependency roles in tools (subclasses of :class:`dlb.cmd.Tool`).

.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.cmd.Tool.Input.RegularFile" -> "dlb.cmd.Tool.Input";
       "dlb.cmd.Tool.Input.Directory" -> "dlb.cmd.Tool.Input";

       "dlb.cmd.Tool.Output.RegularFile" -> "dlb.cmd.Tool.Output";
       "dlb.cmd.Tool.Output.Directory" -> "dlb.cmd.Tool.Output";

       "dlb.cmd.Tool.Input" -> "dlb.cmd.Tool.DependencyRole";
       "dlb.cmd.Tool.Intermediate" -> "dlb.cmd.Tool.DependencyRole";
       "dlb.cmd.Tool.Output" -> "dlb.cmd.Tool.DependencyRole";
   }

Concrete dependency rules can have a *multiplicity*.
A dependency rule with a multiplicity describes a sequence of the same dependency rule without.
The multiplicity expresses the set of the length of the  of members the sequence can take. This set is expressed as a slice
or a single integer.

Example::

    class Example(dlb.cmd.Tool):
        include_search_paths = dlb.cmd.Tool.Input.Directory[:]()  # a sequence of any number of dlb.cmd.Tool.Input.Directory

    example = Example(include_search_paths=['build/out/Generated/', 'src/Implementation/'])
    example.include_search_paths  # (Path('build/out/Generated/'), Path('src/Implementation/'))


Concrete dependency rule classes support the following methods and attributes:

.. attribute:: Cdrc.multiplicity

   The multiplicity of the dependency rule (read-only).

   Is ``None`` or slice of integers with a non-negative ``start`` and a positive ``step``.

.. method:: Cdrc.__getitem__(multiplicity)

   Returns a dependency rule class, which is identical to ``Cdrc``, but has the multiplicity described
   by ``multiplicity``.

   More precisely:
   If ``Cdrc`` is a concrete dependency rule class without a multiplicity,
   every instance ``Cdrc[multiplicity](is_required=..., **kwargs)`` only accepts (finite) iterables other than strings
   as dependencies, where every member of the iterable is accepted by ``Cdrc(is_required=True, **kwargs)``
   and the length ``n`` of the iterable matches the multiplicity.

   If ``multiplicity`` is an integer, ``n`` matches the multiplicity if and only if ``n == multiplicity``.

   If ``multiplicity`` is a slice of integers, ``n`` matches the multiplicity if and only if
   ``n in range(n + 1)[multiplicity]``.

   Examples::

        dlb.cmd.Tool.Output.Directory[3]         # a sequence of exactly three dlb.cmd.Tool.Output.Directory
        dlb.cmd.Tool.Input.RegularFile[1:]       # a sequence of at least one dlb.cmd.Tool.Input.RegularFile
        dlb.cmd.Tool.Output.RegularFile[:2]      # a sequence of at most one dlb.cmd.Tool.Output.RegularFile
        dlb.cmd.Tool.Output.RegularFile[5:21:5]  # a sequence of dlb.cmd.Tool.Output.RegularFile of a length in {5, 15, 20}

   The multiplicity is accessible as a read-only class and instance attribute:

        >>> dlb.cmd.Tool.Output.Directory is None
        True
        >>> dlb.cmd.Tool.Output.Directory().multiplicity is None
        True
        >>> dlb.cmd.Tool.Output.Directory[3].multiplicity
        slice(3, 4, 1)
        >>> dlb.cmd.Tool.Output.Directory[3]().multiplicity
        slice(3, 4, 1)

   On every call with the same multiplicity the same class is returned::

       >>> dlb.cmd.Tool.Output.Directory[:] is dlb.cmd.Tool.Output.Directory[:]
       True

   :param multiplicity: non-negative integer or slice with a non-negative ``start`` and a positive ``step``
   :type multiplicity: int | slice(int)
   :return: ``Cdrc`` with ``Cdrc.multiplicity`` according to  ``multiplicity``

   :raises TypeError: If ``Cdrc.multiplicity`` is not ``None``
   :raises ValueError: If ``multiplicity`` is an negative integer of a slice with a negative ``start`` or a non-positive ``step``

.. method:: Cdrc.is_multiplicity_valid(n)

   :param n: ``None`` or length of iterable
   :type n: None | int
   :return:  ``True`` if ``n`` matches the multiplicity of ``Cdrc``
   :rtype: bool


Concrete dependency rule objects support the following methods and attributes:

.. method:: cdr.__init__(is_required=True, **kwargs)

   :param is_required: Does this dependency require a dependency (other than ``None``)?
   :type is_required: bool

.. method:: cdr.validate(value)

   :param value: The concrete dependency to validate.
   :return: The validated ``value``.

   :raise TypeError: If :attr:`multiplicity` is not ``None`` and ``value`` is not iterable or is a string
   :raise ValueError: If :attr:`is_required` is ``True`` and ``value`` is ``None``

.. attribute:: cdr.is_required

   Does this dependency role require a dependency (other than ``None``)?

   :rtype: bool

.. attribute:: cdr.multiplicity

   The multiplicity of the dependency rule (read-only).

.. method:: cdr.is_more_restrictive_than(other)

   Is this dependency role considered more restrictive than the dependency role ``other``?

   :rtype: bool
