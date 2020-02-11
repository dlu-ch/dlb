:mod:`dlb.ex.tool` --- Dependency-aware tool execution
======================================================
.. module:: dlb.ex
   :synopsis: Dependency-aware tool execution

This module provides classes to represent tools to be executed during the build process (typically by calling
:term:`dynamic helpers <dynamic helper>` like compiler binaries).

Every :term:`tool` is represented by a subclass of :class:`dlb.ex.Tool` that describes its abstract behaviour and the
way it is run (e.g. meaning of command line and output, interaction with file system and environment variables).

Tools are usually parametrized by dependency roles (e.g. input files) and execution parameters.

Each :term:`tool instance` represents a concrete behaviour and can be run in an active context.
Running a tool results in an :term:`python:awaitable` result object.

Tool instances are immutable and hashable and fast to construct; the heavy lifting takes place while the
:term:`tool instance is running<tool instance>`.

Tools are customized by inheritance and defining class attributes.


Tool objects
------------

.. class:: Tool

   A tool declares its *dependency roles* (e.g. ``map_file_dependency``) and *execution parameters*
   (e.g. ``DO_INCLUDE_DEBUG_INFO``, ``PAPER_FORMAT``) as class attributes.

   Every tool instance assigns *concrete dependencies* for the tool's dependency roles
   (e.g. a filesystem path ``'./out/hello.map'`` for a dependency role ``map_file_dependency``),
   while the execution parameters are the same of all instances of the some tool.

   Dependency roles are instances of subclasses of :class:`dlb.ex.Tool.Dependency`.

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



Dependency classes
------------------

A dependency class is a subclass of :class:`dlb.ex.Tool.Dependency`.
Its instances describe *dependency roles* (as attributes of a :class:`Tool`).

The :meth:`Tool.Dependency.validate()` methods of dependency classes are used by :term:`tool instances <tool instance>`
to create *concrete dependencies* from their constructor arguments.

Each dependency role has an *multiplicity specification*:

   a. An instance ``d`` of a dependency class ``D`` created with ``D(...)`` has a ``multiplicity`` of ``None`` which
      means that its concrete dependency must be a *single object* (its type depends on ``D`` only) or ``None``.

   b. An instance ``d`` of a dependency class ``D`` created with ``D[m](...)`` has a ``multiplicity`` of
      ``m`` which means that its concrete dependencies are a *sequence of objects* (their type depends on ``D`` only)
      or ``None``. The accepted number of members is specified by ``m``.

      ``m`` can be any non-negative integer or any meaningful :token:`python:proper_slice` (of non-negative integers).
      A number of members is accepted if and only if is either equal to ``m`` or contained in ``range(n + 1)[m]``.

Example::

    class Tool(dlb.ex.Tool):
        # these are dependency roles of the tool 'Tool':
        include_search_paths = dlb.ex.Tool.Input.Directory[1:]()  # a sequence of at least one dlb.ex.Tool.Input.Directory
        cache_dir_path = dlb.ex.Tool.Input.Directory()  # a single dlb.ex.Tool.Input.Directory

    tool = Tool(include_search_paths=['build/out/Generated/', 'src/Implementation/'])

    # these are concrete dependencies of the tool instance 'tool':
    tool.include_search_paths  # (Path('build/out/Generated/'), Path('src/Implementation/'))
    tool.cache_dir_path  # (Path('build/out/Generated/'), Path('src/Implementation/'))


Dependency classes are organized in an a hierarchy to their meaning to a :term:`tool` with the means of the following
abstract classes:

.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.ex.Tool.Input" -> "dlb.ex.Tool.Dependency";
       "dlb.ex.Tool.Intermediate" -> "dlb.ex.Tool.Dependency";
       "dlb.ex.Tool.Output" -> "dlb.ex.Tool.Dependency";
   }


.. class:: Tool.Input

   A :class:`dlb.ex.Tool.Dependency` that describes an input dependency of a tool.

   The :term:`tool instance` must be :term:`redone <redo>` if it (e.g. the content of a file) has changed compared to
   the state before the last successful redo of the :term:`tool instance`.

   An redo *must not* modify it, successful or not.

.. class:: Tool.Intermediate

   A :class:`dlb.ex.Tool.Dependency` that describes an intermediate dependency of a tool.

   A :term:`redo` of a :term:`tool instance` may modify it in any possible way, provided this does not modify anything
   (e.g. by followed symbolic links). that is not a :class:`dlb.ex.Tool.Intermediate` dependency or
   a :class:`dlb.ex.Tool.Output` dependency of the same tool instance.

.. class:: Tool.Output

   A :class:`dlb.ex.Tool.Dependency` that describes an output dependency of a tool.

   If ``explicit`` is ``True``, a running :term:`tool instance` will remove it before a :term:`redo`.
   A successful redo must generate it (e.g. create a regular file).

   If ``explicit`` is ``False``, a running :term:`tool instance` will *not* remove it before a :term:`redo`.
   An unsuccessful redo must not modify it.


These are all abstract classes and contain inner classes derived from them.
Example: :class:`dlb.ex.Tool.Output.Directory` is a non-abstract dependency class derived
from :class:`dlb.ex.Tool.Output`.


.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.ex.Tool.Input.RegularFile" -> "dlb.ex.Tool.Input";
       "dlb.ex.Tool.Input.NonRegularFile" -> "dlb.ex.Tool.Input";
       "dlb.ex.Tool.Input.Directory" -> "dlb.ex.Tool.Input";
       "dlb.ex.Tool.Input.EnvVar" -> "dlb.ex.Tool.Input";

       "dlb.ex.Tool.Output.RegularFile" -> "dlb.ex.Tool.Output";
       "dlb.ex.Tool.Output.NonRegularFile" -> "dlb.ex.Tool.Output";
       "dlb.ex.Tool.Output.Directory" -> "dlb.ex.Tool.Output";

       "dlb.ex.Tool.Input" -> "dlb.ex.Tool.Dependency";
       "dlb.ex.Tool.Intermediate" -> "dlb.ex.Tool.Dependency";
       "dlb.ex.Tool.Output" -> "dlb.ex.Tool.Dependency";
   }


Concrete dependency role classes support the following methods and attributes:

.. class:: Tool.Dependency(required=True, explicit=True, unique=True)

   If ``required`` is ``True``, a concrete dependency of this dependency role will never be ``None``.

   If ``unique`` is ``True``, concrete dependency whose :attr:`multiplicity` is not ``None`` will never contain
   the the same member more than once (this is ignored if :attr:`multiplicity` is ``None``).

   If ``explicit`` is ``True``, the concrete dependency can and must be fully defined during construct of the
   :term:`tool instance`. Otherwise, it cannot and must not by but automatically assigned by
   :meth:`dlb.ex.Tool.run()`.

   .. param required: is a value other than ``None`` required?
   .. type required: bool
   .. param explicit: explicit dependency?
   .. type explicit: bool
   .. param unique: duplicate-free?
   .. type unique: bool

   Each supported constructor argument is available as a property of the same name.

   .. method:: validate(value, context)

      :param value: The concrete dependency to convert and validate except ``None``
      :type value: Any type the concrete dependency can convert to *T*
      :param context: The concrete dependency to convert and validate except ``None``
      :type context: None | dlb.ex.Context
      :return: The validated ``value`` of type *T*

      :raise TypeError: If :attr:`multiplicity` is not ``None`` and ``value`` is not iterable or is a string

   .. method:: is_more_restrictive_than(other)

      Is this dependency role considered more restrictive than the dependency role ``other``?

      :rtype: bool

   .. attribute:: multiplicity

      The multiplicity of the dependency role (read-only).

      Is ``None`` or a :class:`dlb.ex.mult.MultiplicityRange`.


Input dependency role classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+--------------------------------------------+----------------------------------------------------+
| Dependency role class                      | Keyword arguments of constructor                   |
|                                            +-----------------------+----------------------------+
|                                            | Name                  | Default value              |
+============================================+=======================+============================+
| :class:`dlb.ex.Tool.Input.RegularFile`     | ``cls``               | :class:`dlb.fs.Path`       |
|                                            +-----------------------+----------------------------+
|                                            | ``ignore_permission`` | ``True``                   |
+--------------------------------------------+-----------------------+----------------------------+
| :class:`dlb.ex.Tool.Input.NonRegularFile`  | ``cls``               | :class:`dlb.fs.Path`       |
|                                            +-----------------------+----------------------------+
|                                            | ``ignore_permission`` | ``True``                   |
+--------------------------------------------+-----------------------+----------------------------+
| :class:`dlb.ex.Tool.Input.Directory`       | ``cls``               | :class:`dlb.fs.Path`       |
|                                            +-----------------------+----------------------------+
|                                            | ``ignore_permission`` | ``True``                   |
+--------------------------------------------+-----------------------+----------------------------+
| :class:`dlb.ex.Tool.Input.EnvVar`          | ``restriction``       |                            |
|                                            +-----------------------+----------------------------+
|                                            | ``example``           |                            |
+--------------------------------------------+-----------------------+----------------------------+

In addition to the keyword arguments of the specific constructors described here, all constructors also accept the
keyword arguments of the constructor of :class:`Tool.Dependency`.


.. class:: Tool.Input.RegularFile(cls=dlb.fs.Path)

   Constructs a dependency role for a regular file.

   If ``ignore_permission`` is ``False``, a modification of owner (UID, GID), permission (rwx), existence, type or
   :term:`mtime` is considered a modification of the dependency.
   Otherwise, only a modification of existence, type or :term:`mtime` is considered a modification of the dependency.

   Each single concrete dependency validated by :meth:`validate() <Tool.Dependency.validate()>` is the file's path as an
   instance of ``cls``.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    source_files = dlb.ex.Tool.Input.RegularFile[1:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(source_files=['src/main.cpp'])
      >>> tool.source_files
      (NoSpacePath('src/main.cpp'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path
   :param ignore_permission: ignore permission modifications?
   :type ignore_permission: bool

.. class:: Tool.Input.NonRegularFile(cls=dlb.fs.Path)

   Constructs a dependency role for a filesystem object, that is neither a directory nor a regular file.

   If ``ignore_permission`` is ``False``, a modification of owner (UID, GID), permission (rwx), existence, type or
   :term:`mtime` is considered a modification of the dependency.
   Otherwise, only a modification of existence, type or :term:`mtime` is considered a modification of the dependency.

   Each single concrete dependency validated by :meth:`validate() <Tool.Dependency.validate()>` is the file's path as an
   instance of ``cls``.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    symlinks = dlb.ex.Tool.Input.NonregularFile[:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(symlinks=['src/current'])
      >>> tool.symlinks
      (NoSpacePath('src/current'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path
   :param ignore_permission: ignore permission modifications?
   :type ignore_permission: bool

.. class:: Tool.Input.Directory(cls=dlb.fs.Path)

   Constructs a dependency role for directory.

   If ``ignore_permission`` is ``False``, a modification of owner (UID, GID), permission (rwx), existence, type or
   :term:`mtime` is considered a modification of the dependency.
   Otherwise, only a modification of existence, type or :term:`mtime` is considered a modification of the dependency.

   Each single concrete dependency validated by :meth:`validate() <Tool.Dependency.validate()>` is the directory's path
   as an instance of ``cls``.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    cache_directory = dlb.ex.Tool.Input.Directory(required=False)
      >>> tool = Tool(cache_directory='/tmp/')
      >>> tool.cache_directory
      Path('tmp/')

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path
   :param ignore_permission: ignore permission modifications?
   :type ignore_permission: bool

.. class:: Tool.Input.EnvVar(restriction, example)

   Constructs a dependency role for an environment variable.

   The value of the environment variable named ``name`` (as a string or ``None`` if not defined)
   is validated by matching it to the regular expression ``restriction``.

   Each single concrete dependency validated by :meth:`validate() <Tool.Dependency.validate()>` is a string or
   a dictionary of strings:

      a. If ``restriction`` contains at least one named group: the dictionary of all groups of the validated value
         of the environment variable.

      b. Otherwise, the validated value of the environment variable.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    language = dlb.ex.Tool.Input.EnvVar(
      >>>                   restriction=r'(?P<language>[a-z]{2})_(?P<territory>[A-Z]{2})',
      >>>                   example='sv_SE')
      >>> tool = Tool(language='LANG')
      >>> tool.language['territory']
      'CH'

   :param restriction: regular expression
   :type restriction: str | :class:`python:typing.Pattern`
   :param example: typical value of a environment variable, ``restriction`` must match this
   :type example: str


Concrete output dependency role classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+--------------------------------------------+----------------------------------------------------+
| Dependency role class                      | Keyword arguments of constructor                   |
|                                            +-----------------------+----------------------------+
|                                            | Name                  | Default value              |
+============================================+=======================+============================+
| :class:`dlb.ex.Tool.Output.RegularFile`    | ``cls``               | :class:`dlb.fs.Path`       |
+--------------------------------------------+-----------------------+----------------------------+
| :class:`dlb.ex.Tool.Output.NonRegularFile` | ``cls``               | :class:`dlb.fs.Path`       |
+--------------------------------------------+-----------------------+----------------------------+
| :class:`dlb.ex.Tool.Output.Directory`      | ``cls``               | :class:`dlb.fs.Path`       |
+--------------------------------------------+-----------------------+----------------------------+

In addition to the keyword arguments of the specific constructors described here, all constructors also accept the
keyword arguments of the constructor of :class:`Tool.Dependency`.


.. class:: Tool.Output.RegularFile(cls=dlb.fs.Path)

   Constructs a dependency role for a regular file.

   Each single concrete dependency validated by :meth:`validate() <Tool.Dependency.validate()>` is the file's path
   as an instance of ``cls``.

   Example:

      >>> class Tool(dlb.ex.Tool):
      >>>    object_file = dlb.ex.Tool.Output.RegularFile(cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(object_file=['main.cpp.o'])
      >>> tool.object_file
      (NoSpacePath('main.cpp.o'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

.. class:: Tool.Output.NonRegularFile(cls=dlb.fs.Path)

   Constructs a dependency role for a filesystem object, that is neither a directory nor a regular file.

   Each single concrete dependency validated by :meth:`validate() <Tool.Dependency.validate()>` is the file's path as an
   instance of ``cls``.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    symlinks = dlb.ex.Tool.Output.NonregularFile[:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(symlinks=['dist'])
      >>> tool.symlinks
      (NoSpacePath('src/current'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

.. class:: Tool.Output.Directory(cls=dlb.fs.Path)

   Constructs a dependency role for directory.

   Each single concrete dependency validated by :meth:`validate() <Tool.Dependency.validate()>` is the directory's path
   as an instance of ``cls``.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    html_root_directory = dlb.ex.Tool.Output.Directory(required=False)
      >>> tool = Tool(html_root_directory='html/')
      >>> tool.html_root_directory
      Path('html/')

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path


Exceptions
----------

.. exception:: DefinitionAmbiguityError

   Raised at the definition of a subclass of :class:`dlb.ex.Tool`, when the location is unknown or another subclass of
   :class:`dlb.ex.Tool` was defined before at the same location.