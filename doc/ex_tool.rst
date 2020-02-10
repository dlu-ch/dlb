:mod:`dlb.ex.tool` --- Dependency-aware tool execution
======================================================
.. module:: dlb.ex
   :synopsis: Dependency-aware tool execution

This module provides classes to represent tools to be executed during the build process (typically by calling
:term:`dynamic helpers <dynamic helper>` like compiler binaries).

Every :term:`tool` is represented by a subclass of :class:`dlb.ex.Tool` that describes its abstract behaviour and the
way it is run (e.g. meaning of commandline and output, interaction with file system and environment variables).
Tools are usually parametrized by dependency roles (e.g. input files) and execution parameters.

Each :term:`tool instance` represents a concrete behaviour and can be run in an active context.
Running a tool results in an awaitable result object.

Tool instances are immutable and hashable and fast to construct; the heavy lifting takes place while the
:term:`tool instance is running<tool instance>`.

Tools are customized by inheritance and defining class attributes.


Tool objects
------------

.. class:: Tool

   A tool declares its *dependency roles* (e.g. ``map_file_dependency``) and *execution parameters*
   (e.g. ``DO_INCLUDE_DEBUG_INFO``, ``PAPER_FORMAT``) as class attributes.

   Every tool instance assigns concrete *dependencies* for the tool's dependency roles
   (e.g. a filesystem path ``'./out/hello.map'`` for a dependency role ``map_file_dependency``),
   while the execution parameters are the same of all instances of the some tool.

   Dependency roles are instances of subclasses of :class:`dlb.ex.Tool.DependencyRole`.

   A new tool can be defined by inheriting from one or more other tools.
   When overriding a dependency roles, its overriding value must be of the same type as the overridden value
   and it must be at least as restrictive (e.g. if required dependency must not be overridden by a non-required one).
   When overriding an execution parameters, its overriding value must be of the same type as the overridden value.

   Each subclass of :class:`dlb.ex.Tool` must be defined in a source code location unique among all subclasses of
   :class:`dlb.ex.Tool`. The definition raises :exc:`DefinitionAmbiguityError`, if its location is cannot
   be determined or if another subclass of :class:`dlb.ex.Tool` was defined before at the same location.

   Example::

      class Compiler(dlb.ex.Tool):
         WARNINGS = ('all',)
         source_file = dlb.ex.Tool.Input.RegularFile()
         object_file = dlb.ex.Tool.Output.RegularFile()

      class Linker(dlb.ex.Tool):
         object_files = dlb.ex.Tool.Input.RegularFile[1:]()
         linked_file = dlb.ex.Tool.Output.RegularFile()
         map_file = dlb.ex.Tool.Output.RegularFile(required=False)

      compiler = Compiler(source_file='main.cpp', object_file='main.cpp.o')
      linker = Linker(object_files=[compiler.object_file], linked_file='main')


   At construction of a tool, the dependencies given as keyword arguments to the constructor are validated by the
   tool's dependency roles and made accessible (for reading only) as an attribute with the name of the corresponding
   dependency role and a type determined by the dependency role
   (e.g. :class:`dlb.fs.Path` for :class:`dlb.ex.Tool.Input.RegularFile`)::

      >>> Compiler.object_file  # dependency role
      <dlb.ex.tool.Tool.Input.RegularFile object at ...>

      >>> compiler.object_file  # dependency
      Path('main.cpp.o')

   .. method:: run()

      Run the tool instance in the :term:`active context`.

   .. attribute:: definition_location

      The definition location of the class.

      It is a tuple of the form (``file_path``, ``in_archive_path``, ``lineno``) and uniquely identifies the tool
      among all subclasses of :class:`dlb.ex.Tool`.

      ``in_archive_path`` is ``None``, if the class was defined in an existing Python source file, and ``file_path`` is
      the :func:`python:os.path.realpath()` of this file.

      ``in_archive_path`` is the path relative of the source file in the zip archive, if the class was defined in an
      existing zip archive with a filename ending in ``'.zip'`` (loaded by :mod:`python:zipimport`) and ``file_path`` is
      the :func:`python:os.path.realpath()` of this zip archive.

      ``lineno`` is the 1-based line number in the source file.



Dependency role classes
-----------------------

Dependency roles of tools (subclasses of :class:`Tool`) are instances of subclasses of
:class:`dlb.ex.Tool.DependencyRole`.

.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.ex.Tool.Input" -> "dlb.ex.Tool.DependencyRole";
       "dlb.ex.Tool.Intermediate" -> "dlb.ex.Tool.DependencyRole";
       "dlb.ex.Tool.Output" -> "dlb.ex.Tool.DependencyRole";
   }

They are classified according to their meaning to the tool:

.. class:: Tool.DependencyRole

   Base class of all dependency roles.

.. class:: Tool.Input

   A :class:`dlb.ex.Tool.DependencyRole` that describes an input dependency of a tool.

   The :term:`tool instance` must be rerun if it (e.g. the content of a file) has changed compared to the state before
   it was executed.

.. class:: Tool.Intermediate

   A :class:`dlb.ex.Tool.DependencyRole` that describes an intermediate dependency of a tool.

   Such a dependency (e.g. a directory for caching) is expected not to be accessed while the tool instance
   is running.

.. class:: Tool.Output

   A :class:`dlb.ex.Tool.DependencyRole` that describes an output dependency of a tool.

   The dependency (e.g. a file) is removed before the tool instance starts running if it exists.
   After the execution of the tool it must exist.

These classes are used for structure only; they have no meaningful attributes or methods.
Concrete dependencies can only be assigned to *concrete dependency roles*.
The according classes are inner classes of :class:`dlb.ex.Tool.Input`, :class:`dlb.ex.Tool.Intermediate` and
:class:`dlb.ex.Tool.Output` and derived from these.
Example: :class:`dlb.ex.Tool.Output.Directory` is a concrete output dependency role
(a subclass of :class:`dlb.ex.Tool.Output`).


Concrete dependency role classes and objects
--------------------------------------------

Their objects are used to declare dependency roles in tools (subclasses of :class:`dlb.ex.Tool`).

.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.ex.Tool.Input.RegularFile" -> "dlb.ex.Tool.Input";
       "dlb.ex.Tool.Input.Directory" -> "dlb.ex.Tool.Input";
       "dlb.ex.Tool.Input.EnvVar" -> "dlb.ex.Tool.Input";

       "dlb.ex.Tool.Output.RegularFile" -> "dlb.ex.Tool.Output";
       "dlb.ex.Tool.Output.Directory" -> "dlb.ex.Tool.Output";

       "dlb.ex.Tool.Input" -> "dlb.ex.Tool.DependencyRole";
       "dlb.ex.Tool.Intermediate" -> "dlb.ex.Tool.DependencyRole";
       "dlb.ex.Tool.Output" -> "dlb.ex.Tool.DependencyRole";
   }


A concrete dependency role can have a *multiplicity*.
A dependency role with a multiplicity describes a sequence of the same dependency rule without.
The multiplicity expresses the set of all possible lengths (number of members) the sequence can take.
This set is expressed as a slice or as a single integer.

Example::

    class Example(dlb.ex.Tool):
        include_search_paths = dlb.ex.Tool.Input.Directory[:]()  # a sequence of any number of dlb.ex.Tool.Input.Directory

    example = Example(include_search_paths=['build/out/Generated/', 'src/Implementation/'])
    example.include_search_paths  # (Path('build/out/Generated/'), Path('src/Implementation/'))


Concrete dependency role classes support the following methods and attributes:

.. attribute:: Cdrc.multiplicity

   The multiplicity of the dependency role (read-only).

   Is ``None`` or slice of integers with a non-negative ``start`` and a positive ``step``.

.. method:: Cdrc.__getitem__(multiplicity)

   Returns a dependency role class, which is identical to ``Cdrc``, but has the multiplicity described
   by ``multiplicity``.

   More precisely:
   If ``Cdrc`` is a concrete dependency role class without a multiplicity,
   every instance ``Cdrc[multiplicity](required=..., **kwargs)`` only accepts sequences other than strings
   as dependencies, where every member of the sequence is accepted by ``Cdrc(required=True, **kwargs)``
   and the length ``n`` of the sequence matches the multiplicity.

   If ``multiplicity`` is an integer, ``n`` matches the multiplicity if and only if ``n == multiplicity``.

   If ``multiplicity`` is a slice of integers, ``n`` matches the multiplicity if and only if
   ``n in range(n + 1)[multiplicity]``.

   Examples::

        dlb.ex.Tool.Output.Directory[3]         # a sequence of exactly three dlb.ex.Tool.Output.Directory
        dlb.ex.Tool.Input.RegularFile[1:]       # a sequence of at least one dlb.ex.Tool.Input.RegularFile
        dlb.ex.Tool.Output.RegularFile[:2]      # a sequence of at most one dlb.ex.Tool.Output.RegularFile
        dlb.ex.Tool.Output.RegularFile[5:21:5]  # a sequence of dlb.ex.Tool.Output.RegularFile of a length in {5, 15, 20}

   The multiplicity is accessible as a read-only class and instance attribute:

        >>> dlb.ex.Tool.Output.Directory is None
        True
        >>> dlb.ex.Tool.Output.Directory().multiplicity is None
        True
        >>> dlb.ex.Tool.Output.Directory[3].multiplicity
        slice(3, 4, 1)
        >>> dlb.ex.Tool.Output.Directory[3]().multiplicity
        slice(3, 4, 1)

   On every call with the same multiplicity the same class is returned::

       >>> dlb.ex.Tool.Output.Directory[:] is dlb.ex.Tool.Output.Directory[:]
       True

   ``Cdrc[multiplicity]`` is a subclass of all direct subclasses of ``dlb.ex.Tool.DependencyRole``
   of which ``Cdrc`` is a subclass::

       >>> issubclass(dlb.ex.Tool.Output.Directory[:], dlb.ex.Tool.Output)
       True
       >>> issubclass(dlb.ex.Tool.Output.Directory[:], dlb.ex.Tool.Output.Directory)
       False

   :param multiplicity: non-negative integer or slice with a non-negative ``start`` and a positive ``step``
   :type multiplicity: int | slice(int)
   :return: ``Cdrc`` with ``Cdrc.multiplicity`` according to  ``multiplicity``

   :raises TypeError: If ``Cdrc.multiplicity`` is not ``None``
   :raises ValueError: If ``multiplicity`` is an negative integer of a slice with a negative ``start`` or a non-positive ``step``

.. method:: Cdrc.is_multiplicity_valid(n)

   :param n: ``None`` or length of sequence
   :type n: None | int
   :return:  ``True`` if ``n`` matches the multiplicity of ``Cdrc``
   :rtype: bool


Concrete dependency role objects support the following methods and attributes:

.. method:: cdr.__init__(required=True, [unique=False,] **kwargs)

   :param required: Does this dependency role require a dependency (other than ``None``)?
   :type required: bool
   :param unique:
       (Only if the class has a multiplicity)
       Must the dependency of this dependency role be an iterable representing a duplicate-free sequence?
   :type unique: bool

.. method:: cdr.validate(value)

   :param value: The concrete dependency to validate
   :return: The validated ``value``.

   :raise TypeError: If :attr:`multiplicity` is not ``None`` and ``value`` is not iterable or is a string

.. attribute:: cdr.required

   Does this dependency role require a dependency (other than ``None``)?

   :rtype: bool

.. attribute:: cdr.multiplicity

   The multiplicity of the dependency role (read-only).

.. method:: cdr.is_more_restrictive_than(other)

   Is this dependency role considered more restrictive than the dependency role ``other``?

   :rtype: bool


Concrete input dependency role classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+-------------------------------------------+---------------------------------------------+
| Dependency role class                     | Keyword arguments of constructor            |
|                                           +----------------+----------------------------+
|                                           | Name           | Default value              |
+===========================================+================+============================+
| :class:`dlb.ex.Tool.Input.RegularFile`    | ``required``   | ``True``                   |
|                                           +----------------+----------------------------+
|                                           | ``cls``        | :class:`dlb.fs.Path`       |
|                                           |                |                            |
|                                           |                |                            |
+-------------------------------------------+----------------+----------------------------+
| :class:`dlb.ex.Tool.Input.Directory`      | ``required``   | ``True``                   |
|                                           +----------------+----------------------------+
|                                           | ``cls``        | :class:`dlb.fs.Path`       |
|                                           |                |                            |
|                                           |                |                            |
+-------------------------------------------+----------------+----------------------------+
| :class:`dlb.ex.Tool.Input.EnvVar`         | ``name``       |                            |
|                                           +----------------+----------------------------+
|                                           | ``required``   | ``True``                   |
|                                           |                |                            |
|                                           +----------------+----------------------------+
|                                           | ``propagate``  | ``False``                  |
|                                           +----------------+----------------------------+
|                                           | ``validator``  | ``None``                   |
|                                           |                |                            |
|                                           |                |                            |
|                                           |                |                            |
+-------------------------------------------+----------------+----------------------------+

.. class:: Tool.Input.RegularFile

   .. method:: RegularFile(required=True, cls=dlb.fs.Path)

      Constructs a dependency role for a regular file.
      The dependency is the file's path as an instance of ``cls``.

      Example::

         >>> class Tool(dlb.ex.Tool):
         >>>    source_files = dlb.ex.Tool.Input.RegularFile[1:](cls=dlb.fs.NoSpacePath)
         >>> tool = Tool(source_files=['src/main.cpp'])
         >>> tool.source_files
         (NoSpacePath('src/main.cpp'),)

      :param required: Does this dependency role require a dependency (other than ``None``)?
      :type required: bool
      :param cls: Class to be used to represent the path
      :type cls: dlb.fs.Path

.. class:: Tool.Input.Directory

   .. method:: Directory(required=True, cls=dlb.fs.Path)

      Constructs a dependency role for directory.
      The dependency is the directory's path as an instance of ``cls``.

      Example::

         >>> class Tool(dlb.ex.Tool):
         >>>    cache_directory = dlb.ex.Tool.Input.Directory(required=False)
         >>> tool = Tool(cache_directory='/tmp/')
         >>> tool.cache_directory
         Path('tmp/')

      :param required: Does this dependency role require a dependency (other than ``None``)?
      :type required: bool
      :param cls: Class to be used to represent the path
      :type cls: dlb.fs.Path

.. class:: Tool.Input.EnvVar

   .. method:: EnvVar(name, required=True, propagate=False, validator=None)

      Constructs a dependency role for an environment variable.

      The value of the environment variable named ``name`` (as a string or ``None`` if not defined)
      is validated by ``validator``.

      If ``propagate`` is ``False``, its validated value is assigned to the dependency of this
      dependency role.

      If ``propagate`` is ``True``, a :class:`dlb.ex.PropagatedEnvVar` is assigned to the dependency of this
      dependency role with ``name`` assigned to ``name`` and ``value`` assigned to the
      unchanged value of the environment variable.

      Example::

         >>> class Tool(dlb.ex.Tool):
         >>>    path_envvar = dlb.ex.Tool.Input.EnvVar(name='PATH', propagate=True)
         >>>    territory = dlb.ex.Tool.Input.EnvVar(name='LANG', validator='[a-z]{2}_([A-Z]{2})')
         >>>    uid = dlb.ex.Tool.Input.EnvVar(name='UID', validator=lambda v: int(v, 10))
         >>> tool = Tool()
         >>> tool.path_envvar
         PropagatedEnvVar(name='PATH', value='/usr/bin:/usr/local/bin')
         >>> tool.territory
         'CH'
         >>> tool.uid
         789

      :param name: Name of the environment variable
      :type name: str
      :param required: Does this dependency role require a dependency (other than ``None``)?
      :type required: bool
      :param propagate: Propagate the environment variable`s value unchanged to the dependency of this dependecy role?
      :type propagate: bool
      :param validator:
          If ``None``, every value is considered valid and the validated value is the unmodified value.

          If a (regular expression) string or a compiled regular expression, the value is considered value if and only
          if the entire value matches the regular expression.
          If so, the content of a selected group formed the validated value.
          The selected group is the the named group with the "smallest" name,
          the first unnamed group or the entire value, respectively, in that order.

          If a callable, its is called with the value as its only argument.
          Its return value becomes the validated value.

      :type validator: None | str | regex | callable


Concrete output dependency role classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+-------------------------------------------+---------------------------------------------+
| Dependency role class                     | Keyword arguments of constructor            |
|                                           +----------------+----------------------------+
|                                           | Name           | Default value              |
+===========================================+================+============================+
| :class:`dlb.ex.Tool.Output.RegularFile`   | ``required``   | ``True``                   |
|                                           +----------------+----------------------------+
|                                           | ``cls``        | :class:`dlb.fs.Path`       |
|                                           |                |                            |
|                                           |                |                            |
+-------------------------------------------+----------------+----------------------------+
| :class:`dlb.ex.Tool.Output.Directory`     | ``required``   | ``True``                   |
|                                           +----------------+----------------------------+
|                                           | ``cls``        | :class:`dlb.fs.Path`       |
|                                           |                |                            |
|                                           |                |                            |
+-------------------------------------------+----------------+----------------------------+


.. class:: Tool.Output.RegularFile

   .. method:: RegularFile(required=True, cls=dlb.fs.Path)

      Constructs a dependency role for a regular file.
      The dependency is the file's path as an instance of ``cls``.

      Example:

         >>> class Tool(dlb.ex.Tool):
         >>>    object_file = dlb.ex.Tool.Output.RegularFile(cls=dlb.fs.NoSpacePath)
         >>> tool = Tool(object_file=['main.cpp.o'])
         >>> tool.object_file
         (NoSpacePath('main.cpp.o'),)

      :param required: Does this dependency role require a dependency (other than ``None``)?
      :type required: bool
      :param cls: Class to be used to represent the path
      :type cls: dlb.fs.Path

.. class:: Tool.Output.Directory

   .. method:: Directory(required=True, cls=dlb.fs.Path)

      Constructs a dependency role for directory.
      The dependency is the directory's path as an instance of ``cls``.

      Example::

         >>> class Tool(dlb.ex.Tool):
         >>>    html_root_directory = dlb.ex.Tool.Output.Directory(required=False)
         >>> tool = Tool(html_root_directory='html/')
         >>> tool.html_root_directory
         Path('      html/')

      :param required: Does this dependency role require a dependency (other than ``None``)?
      :type required: bool
      :param cls: Class to be used to represent the path
      :type cls: dlb.fs.Path


Exceptions
----------

.. exception:: DefinitionAmbiguityError

   Raised at the definition of a subclass of :class:`dlb.ex.Tool`, when the location is unknown or another subclass of
   :class:`dlb.ex.Tool` was defined before at the same location.