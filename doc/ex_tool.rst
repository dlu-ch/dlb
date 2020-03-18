:mod:`dlb.ex.tool` --- Dependency-aware tool execution
======================================================

.. module:: dlb.ex.tool
   :synopsis: Dependency-aware tool execution

.. note::

   The entire documented content of this module is also available in :mod:`dlb.ex`.
   For example, :class:`dlb.ex.tool.Tool` is also available by :class:`dlb.ex.Tool <dlb.ex.tool.Tool>`.
   The use of the latter is recommended.


This module provides classes to represent tools to be executed during the build process (typically by calling
:term:`dynamic helpers <dynamic helper>` like compiler binaries).

Every :term:`tool` is represented by a subclass of :class:`Tool` that describes its abstract behaviour and the way it
is run (e.g. meaning of command line and output, interaction with file system and environment variables).

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

   Dependency roles are instances of subclasses of :class:`Tool.Dependency`.

   A new tool can be defined by inheriting from one or more other tools.
   When overriding a dependency roles, its overriding value must be of the same type as the overridden value
   and it must be at least as restrictive (e.g. if required dependency must not be overridden by a non-required one).
   When overriding an execution parameters, its overriding value must be of the same type as the overridden value.

   Each subclass of :class:`Tool` must be defined in a source code location unique among all subclasses of
   :class:`Tool`. The definition raises :exc:`DefinitionAmbiguityError`, if its location is cannot
   be determined or if another subclass of :class:`Tool` was defined before at the same location.

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
   (e.g. :class:`dlb.fs.Path` for :class:`Tool.Input.RegularFile`)::

      >>> Compiler.object_file  # dependency role
      <dlb.ex.Tool.Input.RegularFile object at ...>

      >>> compiler.object_file  # dependency
      Path('main.cpp.o')

   .. method:: run(force_redo=False)

      Run the tool instance in the :term:`active context` and returns a result (proxy) object *result*.

      ``bool(result)`` is ``True`` if a :term:`redo` is performed and ``False`` otherwise.

      A redo is performed if *force_redo* is ``True`` or if it is necessary.

      If a redo is performed, this method returns before the (asynchronous) redo is complete.
      After each of the following actions the redo is guaranteed to be complete (either successfully or
      by raising an exception):

        - read of a "public" attribute of the result proxy object
        - exit of the context :meth:`run()` was called in
        - enter of an inner context of the context :meth:`run()` was called in
        - modification of :attr:`env <dlb.ex.context.Context.env>` or :attr:`helper <dlb.ex.context.Context.helper>` of
          the context :meth:`run()` was called in
        - call of :meth:`run()` of the same tool instance

      The result object contains an attribute for every dependency role of the tool which contains the concrete
      dependencies.

      If ``bool(result)`` is ``True``, all attributes for dependencies have an assigned value.
      If ``bool(result)`` is ``False``, only the attributes for explicit dependencies have an assigned value;
      the value of all attributes for non-explicit dependencies is ``NotImplemented``.

   .. method:: redo(result, context)

      Overwrite this method to implement a new :class:`Tool`.

      *result* is the result object that will by returned by the calling :meth:`run()`.
      *context* is the redo context (see :class:`Tool.RedoContext`).

      Use :meth:`context.execute_helper() <Tool.RedoContext.execute_helper()>` and
      :meth:`context.replace_output() <Tool.RedoContext.replace_output()>`.

      Assign to attributes of *result* to define a non-explicit concrete dependency for the dependency role with the
      same name.

      For a redo to be successful, this method must perform the following tasks:

       - Create all explicit output dependencies
       - Assign values to each required non-explicit dependencies

      For a filesystem object whose path *p* is contained in an output dependency, it is recommended to first write
      to a temporary filesystem object *q* and then replace it with ``context.replace_output(p, q)``.
      This guarantees that no incomplete output dependency is left behind (like an only half-written object file)
      when the :term:`redo` is aborted.

      A filesystem object that is an output dependencies is treated as modified be the redo if it is a non-explicit
      dependency or if it is a explicit dependency that was replaced with `context.replace_output()`.

      Return ``True`` if the next run this :term:`tool instance` should perform a :term:`redo`, regardless of the
      necessity according to its dependencies.

      Example::

         class ATool(dlb.ex.Tool):
            EXECUTABLE = 'atool'

            source_file = dlb.ex.Tool.Input.RegularFile()
            output_file = dlb.ex.Tool.Output.RegularFile()
            included_files = dlb.ex.Tool.Input.RegularFile[:](explicit=False)

            async def redo(self, result, context):
                if ...:
                    raise ValueException('invalid ...')
                with context.temporary() as temp_file_
                   await context.execute_helper(self.EXECUTABLE, ['-o', temp_file, result.source_file])
                   result.included_files = ...
                   context.replace_output(result.output_file, temp_file)

   .. attribute:: definition_location

      The definition location of the class.

      It is a tuple of the form ``(file_path, in_archive_path, lineno)`` and uniquely identifies the tool
      among all subclasses of :class:`Tool`.

      *in_archive_path* is ``None``, if the class was defined in an existing Python source file, and *file_path* is
      the :func:`python:os.path.realpath()` of this file.

      *in_archive_path* is the path relative of the source file in the zip archive, if the class was defined in an
      existing zip archive with a filename ending in :file:`.zip` (loaded by :mod:`python:zipimport`) and *file_path* is
      the :func:`python:os.path.realpath()` of this zip archive.

      *lineno* is the 1-based line number in the source file.

   .. attribute:: fingerprint

      The *permanent local tool instance fingerprint* of this instance.

      This is a :class:`python:bytes` object of fixed size, calculated from all its concrete  dependencies *d* with
      ``d.explicit`` = ``True``.

      If two instances of the same subclass of :class:`Tool` have "similar" explicit dependencies, their
      fingerprints are equal.
      If two instances of the same subclass of :class:`Tool` have explicit dependencies that are not "similar",
      their fingerprints are different with very high probability.

      The explicit dependencies of two instances are considered "similar", if they are equal or differ in a way that
      does *not affect the meaning* of the dependencies while the :term:`tool instance` is running.


Redo context
------------

A redo context is a read-only view for a :class:`dlb.ex.Context <dlb.ex.context.Context>` with some additional
methods related to :term:`dynamic helpers <dynamic helper>` and dependencies.

.. class:: Tool.RedoContext

   A redo context is constructed automatically by :meth:`Tool.run()`.

   .. method:: execute_helper(helper_file, arguments=(), *, cwd=None, expected_returncodes=frozenset([0]),
                              forced_env={}, stdin=None, stdout=None, stderr=None, limit=2**16)

      Execute the *helper_file* with command-line arguments *arguments* in a subprocess with *cwd* as
      its working directory and wait for it to complete.
      The execution is consitered successful if an only if its returncode is one in *expected_returncodes*.

      If *cwd* is not ``None``, is must be the path of directory in the :term:`managed tree` or in :file:`.dlbroot/t/`
      of the :term:`management tree`.
      Otherwise the working tree's root is used as the working directory.

      All members of *arguments* are converted to str objects.

      If a member of *arguments* is a :class:`dlb.fs.Path` object *p* with ``p.is_absolute()`` = ``True``, is is
      replaced by ``str(p.native)``.
      If a member of *arguments* is a :class:`dlb.fs.Path` object *p* with ``p.is_absolute()`` = ``False``, is is
      replaced by ``str(q.native)``, where *q* is *p* expressed relative to the working directory. Is must denote
      a filesystem object in the :term:`managed tree` or in :file:`.dlbroot/t/` of the :term:`management tree`.

      :attr:`env <dlb.ex.context.Context.env>` of this object, modified by *forced_env*, forms the environment for the
      subprocess.

      :param helper_file: :term:`dynamic helper` to be executed as a relative path
      :param arguments: commant-line arguments
      :type arguments: iterable of objects that can be converted to str
      :param cwd: working directory of the subprocess to be started
      :type cwd: ``None`` or a :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param expected_returncodes: expected return codes of the :term:`dynamic helper` *helper_file*
      :type expected_returncodes: collection of integers
      :param forced_env: dictionary of values to override in :attr:`env <dlb.ex.context.Context.env>` or ``None``
      :type forced_env: None | Dict[str, str]
      :param stdin:
         If not ``None``:
         either a file-like object representing a pipe to be connected to the subprocess’s standard input stream using
         :meth:`asyncio.loop.connect_read_pipe()`, or the :const:`asyncio.subprocess.PIPE` constant.
      :param stdout:
         If not ``None``:
         either a file-like object representing the pipe to be connected to the subprocess’s standard output stream
         using :meth:`asyncio.loop.connect_read_pipe()`, or the :const:`asyncio.subprocess.PIPE` constant.
      :param stderr:
         If not ``None``:
         either a file-like object representing the pipe to be connected to the subprocess’s standard error stream using
         :meth:`asyncio.loop.connect_read_pipe()`, or one of :const:`asyncio.subprocess.PIPE` or
         :const:`asyncio.subprocess.STDOUT` constants.
      :param limit:
         the buffer limit for :class:`python:StreamReader` wrappers for :attr:`python:Process.stdout` and
         :attr:`python:Process.stderr` (if :attr:`python:subprocess.PIPE` is passed to *stdout* and *stderr*
         arguments).

      :raises HelperExecutionError: if the subprocess exits with a returncode not in *expected_returncodes*.

      Returns the tuple ``(returncode, stdout_data, stderr_data)``. *returncode* is the returncode
      (contained in *expected_returncodes*). *stdout_data* and *stderr_data* are bytes object with the received data
      from stdout and stderr, respectively.

   .. method:: replace_output(path, source):

      Replace the - existing or non-existent - filesystem object *path* by *source*.
      *path* must be contained in a dependency of the tool instance.

      *path* and *source* must be different filesystem objects.

      After successful completion, *path* exists and *source* does not exist.
      If the parent directory of *path* does not exist, it is created (with all its parent directories).

      The actual operation depends on the corresponding dependency role.
      If is it a :class:`dlb.ex.Tool.Output.RegularFile` with
      :attr:`replace_by_same_content <dlb.ex.Tool.Output.RegularFile.replace_by_same_content>` = ``False`` and *path*
      and *source* both exist with the same content, *path* is no replaced and treated as unchanged.

      If *path* is replaced, this is always done by an atomic operation. If it fails, *path* is either *source*
      afterwards or it does not exist.

      :param path: a path of a future filesystem object in the managed tree
      :type path: :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param source: a path of a filesystem object in the managed tree
      :type source: :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from

      :raises ValueError:
         if *path* is not a :term:`managed tree path` contained in an explicit output dependency or *source* is not a
         :term:`working tree path` of a filesystem object in the :term:`managed tree` or in :file:`.dlbroot/t/` of
         the :term:`management tree` that is different from *path*.


Dependency classes
------------------

A dependency class is a subclass of :class:`Tool.Dependency`.
Its instances describe *dependency roles* (as attributes of a :class:`Tool`).

The :meth:`Tool.Dependency.validate()` methods of dependency classes are used by :term:`tool instances <tool instance>`
to create *concrete dependencies* from their constructor arguments.

Each dependency role has an *multiplicity specification*:

   a. An instance *d* of a dependency class *D* created with ``D(...)`` has a *multiplicity* of ``None`` which
      means that its concrete dependency must be a *single object* (its type depends on *D* only) or ``None``.

   b. An instance *d* of a dependency class *D* created with ``D[m](...)`` has a *multiplicity* of
      *m* which means that its concrete dependencies are a *sequence of objects* (their type depends on *D* only)
      or ``None``. The accepted number of members is specified by *m*.

      *m* can be any non-negative integer or any meaningful :token:`python:proper_slice` (of non-negative integers).
      A number of members is accepted if and only if is either equal to *m* or contained in ``range(n + 1)[m]``.

Example::

    class Tool(dlb.ex.Tool):
        # these are dependency roles of the tool 'Tool':
        include_search_paths = dlb.ex.Tool.Input.Directory[1:]()  # a sequence of at least one dlb.ex.Tool.Input.Directory
        cache_dir_path = dlb.ex.Tool.Input.Directory()  # a single dlb.ex.Tool.Input.Directory

    tool = Tool(include_search_paths=['build/out/Generated/', 'src/Implementation/'])

    # these are concrete dependencies of the tool instance 'tool':
    tool.include_search_paths  # (Path('build/out/Generated/'), Path('src/Implementation/'))
    tool.cache_dir_path  # (Path('build/out/Generated/'), Path('src/Implementation/'))


Dependency classes are organized in an a hierarchy according to their meaning to a :term:`tool` by the means of the
following abstract classes:

.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.ex.Tool.Input" -> "dlb.ex.Tool.Dependency";
       "dlb.ex.Tool.Output" -> "dlb.ex.Tool.Dependency";
   }

.. class:: Tool.Input

   A :class:`Tool.Dependency` that describes an input dependency of a tool.

   The :term:`tool instance` must be :term:`redone <redo>` if it (e.g. the :term:`mtime` of a file) has changed compared
   to the state before the last successful redo of the :term:`tool instance`.

   An redo *must not* modify it, successful or not (the same object can be an output dependency of the same tool
   instance though which *can* be modified).

.. class:: Tool.Output

   A :class:`Tool.Dependency` that describes an output dependency of a tool.

   A successful redo *must* generate it (e.g. create a regular file).


These are all abstract classes and contain inner classes derived from them.
Example: :class:`Tool.Output.Directory` is a non-abstract dependency class derived
from :class:`Tool.Output`.

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
       "dlb.ex.Tool.Output.Object" -> "dlb.ex.Tool.Output";

       "dlb.ex.Tool.Input" -> "dlb.ex.Tool.Dependency";
       "dlb.ex.Tool.Output" -> "dlb.ex.Tool.Dependency";
   }

.. note::

   dlb identifies filesystem objects by their :term:`managed tree path`. It assumes that different managed tree paths
   point to different filesystem objects.

   If a filesystem object serves as an output dependency of one :term:`tool instance` and as an input dependency
   of another: Make sure both dependencies use the same path.
   A :term:`redo miss` could happen otherwise.

   You are always safe without hard links, symbolic links and case-insensitive filesystems.


Concrete dependency role classes support the following methods and attributes:

.. class:: Tool.Dependency(required=True, explicit=True)

   If *required* is ``True``, a concrete dependency of this dependency role will never be ``None``.

   If *explicit* is ``True``, the concrete dependency can and must be fully defined when the :term:`tool instance`
   is created. Otherwise, it cannot and must not be, but automatically assigned by :meth:`Tool.run()`.

   .. param required: is a value other than ``None`` required?
   .. type required: bool
   .. param explicit: explicit dependency?
   .. type explicit: bool

   Each supported constructor argument is available as a property of the same name.

   :raise DependencyError:
      if the arguments of the constructor do not match the declared dependency roles of the class

   .. class:: Value

      A (potentically abstract) class such that ``isinstance(v, Value)`` is ``True`` for each validated single value
      *v* of each instance *t* of this class.

      This is the type of ``t.validate()`` if :attr:`multipliciy` is ``None`` and the type of each member
      of ``t.validate()`` otherwise.

   .. method:: validate(value)

      :param value: The concrete dependency to convert and validate except ``None``
      :type value: Any type the concrete dependency can convert to *T*
      :return: The validated *value* of type *T*

      :raise TypeError: If :attr:`multiplicity` is not ``None`` and *value* is not iterable or is a string

   .. method:: compatible_and_no_less_restrictive(other)

      Is this dependency role an instance of the same class as *other* with a multiplicity and properties no less
      restrictive than the ones of *other*?

      :param other: reference dependency role
      :type other: Tool.Dependency
      :rtype: bool

   .. attribute:: multiplicity

      The multiplicity of the dependency role.

      Is ``None`` or a :class:`dlb.ex.mult.MultiplicityRange`.

   .. method:: tuple_from_value(value)

      Return *value* if :attr:`multiplicity` is ``None`` and a tuple of its members otherwise.

      Example::

         # returns a tuple of t.Value objects or raises an exception:
         >>> v = t.tuple_from_value(t.validate(...))


Input dependency role classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+-------------------------------------+----------------------------------------------------+
| Dependency role class               | Keyword arguments of constructor                   |
|                                     +-----------------------+----------------------------+
|                                     | Name                  | Default value              |
+=====================================+=======================+============================+
| :class:`Tool.Input.RegularFile`     | *cls*                 | :class:`dlb.fs.Path`       |
+-------------------------------------+-----------------------+----------------------------+
| :class:`Tool.Input.NonRegularFile`  | *cls*                 | :class:`dlb.fs.Path`       |
+-------------------------------------+-----------------------+----------------------------+
| :class:`Tool.Input.Directory`       | *cls*                 | :class:`dlb.fs.Path`       |
+-------------------------------------+-----------------------+----------------------------+
| :class:`Tool.Input.EnvVar`          | *name*                |                            |
|                                     +-----------------------+----------------------------+
|                                     | *restriction*         |                            |
|                                     +-----------------------+----------------------------+
|                                     | *example*             |                            |
+-------------------------------------+-----------------------+----------------------------+

In addition to the keyword arguments of the specific constructors described here, all constructors also accept the
keyword arguments of the constructor of :class:`Tool.Dependency`.


.. class:: Tool.Input.RegularFile(cls=dlb.fs.Path)

   Constructs a dependency role for a regular files, identified by their paths.

   If a path is relative, is it treated as relative to
   :attr:`dlb.ex.Context.root_path <dlb.ex.context.Context.root_path>`,
   and it must be :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>`
   (if the path does not contain :file:`..` components, these requirements are met).

   Files outside the :term:`managed tree` are assumed to remain unchanged between :term:`runs of dlb <run of dlb>`.

   The :meth:`validated value <Tool.Dependency.validate()>` of a concrete dependency is the file's path as an instance
   of *cls* if :attr:`multiplicity <Tool.Dependency.multiplicity>` is ``None`` and a tuple of the file's paths
   otherwise.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    source_files = dlb.ex.Tool.Input.RegularFile[1:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(source_files=['src/main.cpp'])
      >>> tool.source_files
      (NoSpacePath('src/main.cpp'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: Tool.Input.NonRegularFile(cls=dlb.fs.Path)

   Constructs a dependency role for filesystem objects that are neither directories nor regular files,
   identified by their paths.

   If a path is relative, is it treated as relative to
   :attr:`dlb.ex.Context.root_path <dlb.ex.context.Context.root_path>`,
   and it must be :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>`
   (if the path does not contain :file:`..` components, these requirements are met).

   Files outside the :term:`managed tree` are assumed to remain unchanged between :term:`runs of dlb <run of dlb>`.

   The :meth:`validated value <Tool.Dependency.validate()>` of a concrete dependency is the file's path as an instance
   of *cls* if :attr:`multiplicity <Tool.Dependency.multiplicity>` is ``None`` and a tuple of the file's paths
   otherwise.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    symlinks = dlb.ex.Tool.Input.NonRegularFile[:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(symlinks=['src/current'])
      >>> tool.symlinks
      (NoSpacePath('src/current'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: Tool.Input.Directory(cls=dlb.fs.Path)

   Constructs a dependency role for directories, identified by their paths.

   If a path is relative, is it treated as relative to
   :attr:`dlb.ex.Context.root_path <dlb.ex.context.Context.root_path>`,
   and it must be :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>`
   (if the path does not contain :file:`..` components, these requirements are met).

   Directories outside the :term:`managed tree` are assumed to remain unchanged between :term:`runs of dlb <run of dlb>`.

   The :meth:`validated value <Tool.Dependency.validate()>` of a concrete dependency is the directory's path as an
   instance of *cls* if :attr:`multiplicity <Tool.Dependency.multiplicity>` is ``None`` and a tuple of the
   directory's paths otherwise.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    cache_directory = dlb.ex.Tool.Input.Directory(required=False)
      >>> tool = Tool(cache_directory='/tmp/')
      >>> tool.cache_directory
      Path('tmp/')

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: Tool.Input.EnvVar(name, restriction, example)

   Constructs a dependency role for a environment variable named *name*.
   It must not have a multiplicity (other than ``None``).

   If *explicit* is ``False``, the value assign in the constructor of the :term:`tool instance` is used for all
   future runs of the tool instance.
   Otherwise, the current value of the :term:`active context` is used each time :meth:`Tool.run()` is called.

   The value of the environment variable is valid if it a string that matches the regular expression *restriction*,
   or if it is ``None`` and *required* is ``False``.

   The :meth:`validated value <Tool.Dependency.validate()>` of a concrete dependency is a :class:`Value` instance
   with the environment variable's name and value.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    language = dlb.ex.Tool.Input.EnvVar(
      >>>                   name='LANG',
      >>>                   restriction=r'(?P<language>[a-z]{2})_(?P<territory>[A-Z]{2})',
      >>>                   example='sv_SE')
      >>>     flags = dlb.ex.Tool.Input.EnvVar(name='CFLAGS', restriction=r'.+', example='-Wall')
      >>> tool = Tool(language='de_CH')  # use 'de_CH' as value of the environment variable for all
      >>> tool.language.value['territory']
      'CH'
      >>> tool.flags
      NotImplemented
      >>> tool.run().flags.value  # assuming dlb.ex.Context.env['CFLAGS'] of '-O2'
      '-O2'

   :param restriction: regular expression
   :type restriction: str | :class:`python:typing.Pattern`
   :param example: typical value of a environment variable, *restriction* must match this
   :type example: str

   .. class:: Value

      A :class:`dataclasses.dataclass` object with the following attributes:

      .. attribute:: name

         The name of the environment variable, as in the corresponding concrete dependency.

      .. attribute:: raw

         The value of the environment variable.

      .. attribute:: groups

         The named groups of *restriction* of the corresponding concrete dependency when matched against *raw*.


Concrete output dependency role classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+-------------------------------------+--------------------------------------------------------+
| Dependency role class               | Keyword arguments of constructor                       |
|                                     +---------------------------+----------------------------+
|                                     | Name                      | Default value              |
+=====================================+===========================+============================+
| :class:`Tool.Output.RegularFile`    | *cls*                     | :class:`dlb.fs.Path`       |
|                                     | *replace_by_same_content* | ``True``                   |
+-------------------------------------+---------------------------+----------------------------+
| :class:`Tool.Output.NonRegularFile` | *cls*                     | :class:`dlb.fs.Path`       |
+-------------------------------------+---------------------------+----------------------------+
| :class:`Tool.Output.Directory`      | *cls*                     | :class:`dlb.fs.Path`       |
+-------------------------------------+---------------------------+----------------------------+
| :class:`Tool.Output.Object`         |                           |                            |
+-------------------------------------+---------------------------+----------------------------+

In addition to the keyword arguments of the specific constructors described here, all constructors also accept the
keyword arguments of the constructor of :class:`Tool.Dependency`.


.. class:: Tool.Output.RegularFile(cls=dlb.fs.Path, replace_by_same_content=True)

   Constructs a dependency role for regular files in the :term:`managed tree`, identified by their paths.

   If a path is relative, is it treated as relative to
   :attr:`dlb.ex.Context.root_path <dlb.ex.context.Context.root_path>`,
   and it must be :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>`
   (if the path does not contain :file:`..` components, these requirements are met).

   The :meth:`validated value <Tool.Dependency.validate()>` of a concrete dependency is the file's path as an instance
   of *cls* if :attr:`multiplicity <Tool.Dependency.multiplicity>` is ``None`` and a tuple of the file's paths
   otherwise.

   If *replace_by_same_content* is ``False`` for a dependency role containing *p*, ``context.replace_output(p, q)``
   in :meth:`redo(..., context) <dlb.ex.Tool.redo()>` does not replace *p* if *p* and *q* both exist as accessible
   regular files and have the same content.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    object_file = dlb.ex.Tool.Output.RegularFile(cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(object_file=['main.cpp.o'])
      >>> tool.object_file
      (NoSpacePath('main.cpp.o'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: Tool.Output.NonRegularFile(cls=dlb.fs.Path)

   Constructs a dependency role for filesystem objects in the :term:`managed tree` that are neither directories nor
   regular files, identified by their paths.

   If a path is relative, is it treated as relative to
   :attr:`dlb.ex.Context.root_path <dlb.ex.context.Context.root_path>`,
   and it must be :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>`
   (if the path does not contain :file:`..` components, these requirements are met).

   The :meth:`validated value <Tool.Dependency.validate()>` of a concrete dependency is the file's path as an instance
   of *cls* if :attr:`multiplicity <Tool.Dependency.multiplicity>` is ``None`` and a tuple of the file's paths
   otherwise.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    symlinks = dlb.ex.Tool.Output.NonRegularFile[:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(symlinks=['dist'])
      >>> tool.symlinks
      (NoSpacePath('src/current'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: Tool.Output.Directory(cls=dlb.fs.Path)

   Constructs a dependency role for directories in the :term:`managed tree`, identified by their paths.

   If a path is relative, is it treated as relative to
   :attr:`dlb.ex.Context.root_path <dlb.ex.context.Context.root_path>`,
   and it must be :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>`
   (if the path does not contain :file:`..` components, these requirements are met).

   The :meth:`validated value <Tool.Dependency.validate()>` of a concrete dependency is the directory's path as an
   instance of *cls* if :attr:`multiplicity <Tool.Dependency.multiplicity>` is ``None`` and a tuple of the
   directory's paths otherwise.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    html_root_directory = dlb.ex.Tool.Output.Directory(required=False)
      >>> tool = Tool(html_root_directory='html/')
      >>> tool.html_root_directory
      Path('html/')

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: Tool.Output.Object()

   Constructs a dependency role for any Python object other than ``None`` and ``NotImplemented``.
   It must not be explicit.

   The :meth:`validated value <Tool.Dependency.validate()>` of a concrete dependency is a
   :func:`deep copy <python:copy.deepcopy()>` of the value.

   .. class:: Value

      Is :class:`python:typing.Any`.


Exceptions
----------

.. exception:: DefinitionAmbiguityError

   Raised at the definition of a subclass of :class:`Tool`, when the location is unknown or another subclass of
   :class:`Tool` was defined before at the same location.

.. exception:: DependencyError

   Raised when a running :term:`tool instance` detects a problem with its dependencies before a :term:`redo`.

.. exception:: ExecutionParameterError

   Raised when a running :term:`tool instance` detects a problem with its execution parameters before a :term:`redo`.

.. exception:: RedoError

   Raised when a running :term:`tool instance` detects a problem with its dependencies during or after a :term:`redo`.

.. exception:: HelperExecutionError

   Raised, when the execution of a :term:`dynamic helper` file failed.
