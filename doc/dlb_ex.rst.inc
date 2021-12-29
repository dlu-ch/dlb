:mod:`dlb.ex` --- Execution contexts and dependency-aware tool execution
========================================================================

.. module:: dlb.ex
   :synopsis: Execution of tool instances


Context objects
---------------

An :term:`(execution) context <context>` describes how running :term:`tool instances <tool instance>` shall interact
with the execution environment outside the :term:`working tree` and with each other.
E.g:

- number of asynchronously running :term:`tool instances <tool instance>`
- synchronization of :term:`redos <redo>`
- search paths for :term:`dynamic helper` files
- set of environment variables for :term:`tool instances <tool instance>`

It also helps with filesystem abstraction (e.g. :term:`working tree time` or
:term:`working tree paths <working tree path>`).

A context is represented as an instance of :class:`dlb.ex.Context` used as a context manager.
The context is entered with the call of :meth:`__enter__ <object.__enter__>` and exited with the return
of :meth:`__exit__ <object.__exit__>`.

Contexts can be nested::

   import dlb.ex

   # no active context

   with dlb.ex.Context():                # A: root context, outer context of B, C, D
       # A is the active context
       with dlb.ex.Context():            # B: inner context of A, outer context of C
           # B is the active context
           with dlb.ex.Context():        # C: inner context of A, B
              # C is the active context
       with dlb.ex.Context():            # D: inner context of A
           # D is the active context
       # A is the active context

   # no active context

Combine contexts with :class:`message clusters <dlb.di.Cluster>` to describe what happens in the context::

   with dlb.di.Cluster('this happens in the context'), dlb.ex.Context():
       ...


.. class:: Context(*, path_cls=dlb.fs.Path, max_parallel_redo_count=1, find_helpers=None)

   An instance does nothing unless used as a :term:`python:context manager`.

   When used as a context manager, it embodies an (execution) context and :term:`activates <active context>` it:

   a. a :term:`root context`, if :term:`dlb is not yet running <run of dlb>`;

   b. an inner context of the :term:`active context`, otherwise.

   When a root context is entered, the working directory of the Python process must be a :term:`working tree`'s root
   whose absolute path does not contain unresolved symbolic link.

   When a context (root or not) is entered, the path of the :term:`working tree`'s root must be representable as
   as *path_cls*. This allows you to impose :ref:`restrictions <dlb-fs-restricting-paths>` on the accepted paths.

   If *find_helpers* is ``None`` for a :term:`root context`, ``True`` is used instead.
   If *find_helpers* is ``None`` for an active context that is not the :term:`root context`, *find_helpers* of
   the :term:`root context` is used.

   :param path_cls: the subclass of :class:`dlb.fs.Path` to be used to represent the :term:`working tree`'s root
   :type path_cls: dlb.fs.Path
   :param max_parallel_redo_count: maximum number of redos started in this context than can be pending at the same time
   :type max_parallel_redo_count: int
   :param find_helpers: are dynamic helpers not defined explicitly to be searched for in :attr:`executable_search_paths`?
   :type find_helpers: None | bool
   :raises TypeError: if *path_cls* is not a subclass of :class:`dlb.fs.Path`

   Entering or exiting a context may raise the following exceptions:

   +-----------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | exception                   | meaning                                                                     | when                           |
   +=============================+=============================================================================+================================+
   | :exc:`NoWorkingTreeError`   | the working directory is not a :term:`working tree`'s root                  | entering :term:`root context`  |
   +-----------------------------+-----------------------------------------------------------------------------+                                |
   | :exc:`ManagementTreeError`  | the :term:`management tree` cannot be setup inside the :term:`working tree` |                                |
   +-----------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | :exc:`ValueError`           | the :term:`working tree`'s root path violates the requested restrictions    | entering (any) context         |
   +-----------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | :exc:`ContextNestingError`  | the contexts are not properly nested                                        | exiting (any) context          |
   +-----------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | :exc:`WorkingTreeTimeError` | :term:`working tree time` behaved unexpectedly                              | exiting :term:`root context`   |
   +-----------------------------+-----------------------------------------------------------------------------+--------------------------------+

   .. note::
      You probably want to use the :term:`active context` only.
      Use :attr:`dlb.ex.Context.active` to get it.

   The :class:`Context` class supports the following methods and attributes:

   .. attribute:: active

      The :term:`active context`.

      This is a class attribute to be used like this::

         with dlb.ex.Context:
             ... = dlb.ex.Context.active.root_path
             ... = dlb.ex.Context.active.find_path_in(...)

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. attribute:: root_path

      The absolute path of the :term:`working tree`'s root.

      It is an instance of :attr:`Context.active.path_cls <Context.path_cls>` and
      is representable as an instance of :attr:`path_cls <Context.path_cls>` of the :term:`active context` and every
      possible outer context.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. attribute:: executable_search_paths

      A duplicate-free tuple of absolute directory paths where this process should look for executables according to
      the operating system.

      It is compiled from the members :func:`python:os.get_exec_path()` when the root context is entered.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. attribute:: path_cls

      The subclass of :class:`.dlb.fs.Path` as defined in the constructor.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. attribute:: max_parallel_redo_count

      The maximum number of redos started in this context than can be pending at the same time as defined in the
      constructor.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. attribute:: find_helpers

      Find dynamic helpers not defined explicitly in :attr:`executable_search_paths`?
      As defined in the constructor.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. attribute:: env

      The :ref:`environment variable dictionary object <dlb-ex-environment-variable-dictionary-objects>` with
      this context as its associated :term:`context`.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. attribute:: helper

      The dynamic helper dictionary object with this context as its associated :term:`context`.

      The dynamic helper dictionary object maps :term:`dynamic helpers <dynamic helper>` to absolute paths, either
      explicitly or implicitly with the help of :meth:`find_path_in()`.

      If the :term:`active context` and the :term:`root context` both have :attr:`find_helpers` == ``False``
      and no paths was explicitly assigned to the dynamic helper *p* in the active context or one of its outer contexts,
      a look-up with ``dlb.ex.Context.active.helper[p]`` performs a search with
      ``dlb.ex.Context.active.find_path_in(p)``.
      (Each such search is performed only once for a given path; the result is stored.)

      Examples::

         >>> dlb.ex.Context.active.helper['gcc']
         Path('/usr/bin/gcc')

         >>> dlb.ex.Context.active.helper['gcc'] = '/usr/local/bin/my-very-own-very-special-gcc'  # set the path explicitly
         >>> dlb.ex.Context.active.helper['gcc']
         Path('/usr/local/bin/my-very-own-very-special-gcc')

         >>> dlb.ex.Context.active.helper['tmp/'] = 'out/t/'  # relative path: relative to the working tree's root path
         >>> dlb.ex.Context.active.helper['tmp/']  # with '/home/schmutzli/projects/esel' as the working tree's root
         Path('/home/schmutzli/projects/esel/out/t')

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. method:: find_path_in(path, search_prefixes=None)

      Find the first existing and accessible *path* in *search_prefixes* and return its absolute path.
      Returns ``None`` if *path* is not found in *search_prefixed*.

      If *path* is a :class:`dlb.fs.Path` with ``path.is_dir() == True``, existing non-directories in
      *search_prefixes* are ignored.
      If *path* is a :class:`dlb.fs.Path` with ``path.is_dir() == False``, existing directories in
      *search_prefixes* are ignored.

      Relative paths in *search_prefixes* are treated as relative to :attr:`root_path`.

      If *search_prefixes* is ``None``, :attr:`executable_search_paths` is used instead.

      Does not raise :exc:`OSError`.

      :param path: the relative path to find
      :type path: :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param search_prefixes: paths of directories to search in
      :type search_prefixes: an iterable other than :class:`python:str` or :class:`python:bytes` or ``None``
      :return: an absolute path or ``None``.

   .. attribute:: working_tree_time_ns

      The current :term:`working tree time` in nanoseconds as an integer.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. attribute:: is_working_tree_case_sensitive

      Return ``True`` if the filesystem that contains the working tree is case-sensitive, and ``False`` otherwise.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. method:: working_tree_path_of(path, *, is_dir=None, existing=False, collapsable=False, \
                                    allow_nontemporary_management=False, allow_temporary=False)

      Return the :term:`managed tree path` of the *path* of a filesystem object in the :term:`managed tree`.

      For *path* to be considered as the path of a filesystem object in the :term:`managed tree`, *path* must either
      be a relative path or it must have :attr:`root_path` as a prefix.

      The arguments *existing* and *collapsable* describe the assumptions on the filesystem content that may be used to
      increase the speed and reduce the number of filesystem accesses.

      If *existing* and *collapsable* are ``True`` and *path* is relative, the filesystem is never accessed.

      If *existing* is ``False``, :meth:`is_dir() <dlb.fs.Path.is_dir()>` of the returned path reflects the type
      of the actual filesystem object. Raises :exc:`dlb.ex.WorkingTreePathError` if *path* does not exist.

      If *allow_nontemporary_management* is ``True``, the resulting path may denote a filesystem object in
      the :term:`management tree` except in :file:`.dlbroot/t`.
      If *allow_temporary* is ``True``, the resulting path may denote a filesystem object in :file:`.dlbroot/t`
      of the :term:`management tree`.

      Does *not* raise :exc:`OSError`.

      :param path: a path of a filesystem object in the managed tree
      :type path: :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param is_dir: ``True`` if this is a directory path, ``False`` if not and ``None`` for derivation from *path*
      :type is_dir: NoneType | bool
      :param existing: assume that all involved filesystem objects exist?
      :type existing: bool
      :param collapsable: assume that any relative to the working tree root is :term:`collapsable <collapsable path>`?
      :type collapsable: bool
      :param allow_nontemporary_management:
         is the path permitted to denote a filesystem object the :term`management tree` except ones
         in :file:`.dlbroot/t`?
      :type allow_nontemporary_management: bool
      :param allow_temporary:
         is the path permitted to denote a filesystem object in :file:`.dlbroot/t` of the :term:`management tree`?
      :type allow_temporary: bool
      :return: a :class:`dlb.fs.Path` *p* with ``p.is_absolute() == False`` and ``p.is_normalized() == True``
      :rtype: class of *path* if *path* is a :class:`dlb.fs.Path`, or :class:`dlb.fs.Path` otherwise

      :raises WorkingTreePathError:
          if *path* does not exist in the parts of the :term:`working tree` that are described by
          *allow_nontemporary_management* and *allow_temporary*
      :raises ValueError: if the resulting path is not representable
      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. method:: temporary(*, suffix='', is_dir=False)

      Return a context manager, representing a temporary regular file (for *is_dir* = ``False``) or a
      temporary directory (for *is_dir* = ``True``) in the :term:`management tree` with a unique path.

      Usage example::

         with context.temporary(suffix='.o') as p:
             ...  # an empty file with absolute path *p* (as a dlb.fs.Path) exists

         ... = context.temporary().path  # just get the absolute path, do not create the file

      The *path* attribute of the context manager is an absolute path in the same directory for all calls in the
      :term:`root context` as a :class:`dlb.fs.Path` object.
      The :meth:`__enter__ <object.__enter__>` method of the context manager returns *path*.

      The last component of *path* is unique among all calls in the :term:`root context` (and is therefore called
      its *unique path component*).
      ``path.is_dir()`` is *is_dir*.
      The path of the :term:`working tree's root <working tree>` is ``path[:-3]``.

      The unique path component starts with a lower-case letter and ends with *suffix*.
      It contains only lower-case letters and decimal digits between its first characters and the suffix.
      If *suffix* is not empty, is must start with a character from :data:`python:string.punctuation` and must not
      contain ``'/'``.
      The unique path component without the *suffix* is at most 12 characters long for the first 2**61 calls.

      When used as a context manager, an empty regular file or directory with *path* is created when entered and removed
      (with its content) on exit. Raises :exc:`FileExistsError` if the regular file or directory exists.

      :param suffix: suffix of the unique path component
      :type suffix: str
      :type is_dir: bool

      :raises ValueError: if *suffix* is invalid
      :raises FileExistsError: if the regular file or directory exists (when used as content manager)
      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. method:: summary_of_latest_runs(*, max_count=1)

      Return a list of information on previous :term:`runs of dlb <run of dlb>` according to the :term:`run-database`
      used by the current :term:`root context`.

      If there is information on more than *max_count*, the *max_count* runs with the latest UTC datetime of their start
      are picked.

      .. note::
         There is no guaranteed that all the datetimes differ.

      Each member of the returned list is a tuple ``(start_time, duration_ns, tool_inst_run_count, tool_inst, redo_count)``.
      *start_time* is the UTC datetime of the run's start as a :class:`datetime.datetime`.
      *duration_ns* is the duration of the run in nanoseconds as non-negative integer.
      *tool_inst_run_count* is the total number of runs of tool instances in the dlb run as a non-negative integer.
      *redo_count* is the total number of redos of tool instances in the dlb run as a non-negative integer not greater
      than *tool_inst_run_count*.

      :param max_count: maximum number of runs
      :rtype: list of tuples

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`


.. _dlb-ex-environment-variable-dictionary-objects:
.. _dlb-ex-environment-variable-accessors:

Environment variables
---------------------

The environment variable dictionary object *env* returned by :attr:`c.env <Context.env>` for a :term:`context` *c*
is a dictionary-like object of all environment variables defined in *c*.
*c* is called the associated :term:`context` of *env*.

In addition, the environment variable dictionary object manages the declaration, validation, and assignment of
environment variables that are effective for all :term:`tool instances <tool instance>`.

Environment variables behave like optional variables in a statically typed language:
They need to be *declared* before a value can be assigned.
A declared environment variable with an assigned value is called *defined*.

Environment variables can be declared and defined only in the currently *active* context.
When an inner context is entered, it *inherits* the current declaration and, if available, the current value of each
environment variable from its direct outer context.
An inherited environment variable can be redeclared, redefined, or undefined in the inner context without effecting
the environment variable in any outer contexts.

There is no implicit connection between environment variables in a context and environment variables of the
process running dlb (:data:`os.environ`).

Example::

   with dlb.ex.Context():

       # declare the environment variable 'LANG' in the context (and all its future inner contexts) and
       # assign value of OS (process) environment variable 'LANG' if defined:
       dlb.ex.Context.active.env.declare(
           'LANG',
           pattern=r'[a-z]{2}_[A-Z]{2}',  # if defined, value must satisfy this regular expression
           example='sv_SE'
       ).set_from_os(
           required=False,
           expected="expected language (ISO 639-1) and "  # optional description of expected value
                    "territory (ISO 3166-1 alpha-2)"      # for exception message if value invalid
       )

       # now the environment variable is either undefined or matches the regular expression given
       # (in this context and all future inner contexts)

       # value satisfies the validation pattern or KeyError is raised:
       ... = dlb.ex.Context.active.env['LANG']

       dlb.ex.Context.active.env['LANG'] = 'de_AT'

       with dlb.ex.Context():

           # redeclare with different regular expression in this context
           # (without affecting the declaration and the value in the outer context)
           dlb.ex.Context.active.env.declare('LANG', pattern='(?P<language>de).*', example='de_CH').set_from_outer()

           ... = dlb.ex.Context.active.env['LANG']  # 'de_AT'
           del dlb.ex.Context.active.env['LANG']

           dlb.ex.Context.active.env['LANG'] = 'de_CH'
           # dlb.ex.Context.active.env['LANG'] = 'fr_FR'  # would raise ValueError

       ... = dlb.ex.Context.active.env['LANG']  # 'de_AT'

       del dlb.ex.Context.active.env['LANG']  # undefine 'LANG'
       dlb.ex.Context.active.env['LANG'] = 'fr_FR'  # ok

Environment variable dictionary objects support the following methods and attributes:

.. method:: EnvVarDict.declare(name, *, pattern, example=None)

   Declare an environment variable of name *name* and restrict its accepted value to values that
   match the given validation pattern.

   After declaration, the environment variable is undefined, i.e. it has no value.
   It can be set to any value that matches the regular expression *pattern*, for example with one of the `set` methods
   of the returned environment variable accessor.

   :param name: (non-empty) name of the environment variable
   :type name: str
   :param pattern: validation pattern for value as a regular expression
   :type pattern: str | :class:`python:typing.Pattern`
   :param example: typical value of an environment variable, *pattern* must match this
   :type example: str
   :return: accessor for the declared environment variable
   :rtype: EnvVarAccessor

   :raises ValueError: if *example* does not match *pattern*
   :raises ContextModificationError: if the associated context is not an :term:`active context`

.. method:: EnvVarDict.get(name, default=None)

   Return its value if *name* is the name of a defined environment variable in the associated :term:`context`,
   else *default*.

   :param name: non-empty name of an environment variable
   :type name: str

   :raises TypeError: if *name* is not a string
   :raises ValueError: if *name* is an empty string

.. method:: EnvVarDict.items()

   Return a new view of the dictionary’s items (name, value) pairs of all defined environment variables.

.. describe:: name in env

   Return `True` if there is an environment variable named *name* defined in *env* or in any of its outer contexts,
   else `False`.

.. describe:: name not in env

   Equivalent to ``not name in env``

.. describe:: env[name] = value

   Define *value* as the value of a declared environment variable named *name* in the associated :term:`context`.

   :raises AttributeError: if *name* is not declared in the associated :term:`context`
   :raises ValueError:
     if *name* is declared in the associated :term:`context` or one of its outer contexts
     but the associated validation pattern in the associated context or in one of its any outer contexts does not
     match *value*
   :raises ContextModificationError: if the associated context is not an :term:`active context`

.. describe:: del env[name]

   Undefine a defined environment variable named *name* in the associated :term:`context` and all its future
   inner contexts.

   :raises KeyError: if *name* is not defined in the :term:`context`
   :raises ContextModificationError: if the associated context is not an :term:`active context`

Declared environment variables in the active context can be accessed and manipulated by corresponding
*environment variable accessors*.

.. class:: EnvVarAccessor

   A :class:`dlb.ex.EnvVarAccessor` represents an accessor for a potential environment variables of a given name
   in the active :term:`context`.

   Its main purpose is to set values of declared environment variable from different sources
   (e.g. OS environment variables) without repetition and with expressive exception messages in case of errors.

   Environment variable accessors are created

   - by the declaration of environment variables with
     :meth:`dlb.ex.Context.active.env.declare() <EnvVarDict.declare>`; or
   - by direct construction.

   The :class:`dlb.ex.EnvVarAccessor` class supports the following methods and attributes:

   .. method:: EnvVarAccessor(name)

      Construct an environment variable accessor for a potential environment variable with name *name*
      in the active :term:`context`.

      :raises TypeError: if *name* is not a string
      :raises ValueError: if *name* is an empty string

   .. attribute:: name

      Name of the potential environment variable to be accessed by this object.

   .. method:: get(*, default=None, require_definition=False)

      Return the value of environment variable :attr:`name` in the active :term:`context`, or *default* if
      it is not defined.

      :return: defined value as `str` or *default*
      :raises AttributeError: if not declared and *require_definition* is `True`
      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. method:: is_declared()

      Return ``True`` if :attr:`name` is the name of an environment variable declared in the active :term:`context`.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. method:: is_defined()

      Return ``True`` if :attr:`name` is the name of an environment variable defined in the active :term:`context`.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`

   .. method:: set(value, *, required=True)

      If *value* is not `None`, define *value* as the value of a environment variable :attr:`name` in
      the active :term:`context`.
      Otherwise (and if *required* is `False`), undefine environment variable :attr:`name` in
      the active context.

      :raises AttributeError: if :attr:`name` is not declared in the active :term:`context`
      :raises ValueError: if *value* is `None` and *required* is `True`
      :raises ValueError:
        if :attr:`name` is declared in the active :term:`context` but the associated validation pattern
        does not match *value*

   .. method:: set_from_outer(*, required=True)

      If the environment variable :attr:`name` is defined in the (direct) outer context,
      (re)define it in the active context with the same value.

      :raises AttributeError: if :attr:`name` is not declared in the active :term:`context`
      :raises KeyError:
        if :attr:`name` is not defined in the (direct) outer context :term:`context` and *required* is `True`
      :raises ValueError:
        if :attr:`name` is defined in (direct) outer context as *v* but the associated validation pattern
        does not match *v*

   .. method:: set_from_os(self, name=None, *, required=True, default=None, expected=None)

      If a OS environment variable *name* - or :attr:`name` if *name* is `None` - is defined in :data:`os.environ`,
      (re)define it in the active context with the same value.

      :raises AttributeError: if :attr:`name` is not declared in the active :term:`context`
      :raises KeyError:
        if OS environment variable *name* - or :attr:`name` if *name* is `None` - is not defined
        and *required* is `True`
      :raises ValueError:
        if OS environment variable *name* - or :attr:`name` if *name* is `None` - is defined as *v*
        but the validation pattern associated with :attr:`name` does not match *v*


Tool objects
------------

Every :term:`tool` is represented by a subclass of :class:`Tool` that describes its abstract behaviour and the way it
is run (e.g. meaning of command line and output, interaction with file system and environment variables).

Tools are parametrized by optional dependency roles (e.g. input files) and execution parameters.

Each :term:`tool instance` represents a concrete behaviour and can be run in an active context.
Running a tool results in an :term:`python:awaitable` result object.

Tool instances are immutable and hashable and fast to construct; the heavy lifting takes place while the
:term:`tool instance is running<tool instance>`.

Tools are customized by inheritance and defining class attributes.

.. class:: Tool

   A tool declares its *dependency roles* and *execution parameters* as class attributes.
   The name of a dependency role must consist of at least two lower-case words separated by ``_`` (e.g. ``map_file``).
   The name of an execution parameters must consist of lower-case words separated by ``_`` (e.g. ``WARNINGS``,
   ``VERSION_PARAMETERS``).

   Dependency roles are instances of subclasses of :class:`Dependency`.

   Every tool instance assigns *concrete dependencies* for the tool's dependency roles
   (e.g. a filesystem path ``'./out/hello.map'`` for a dependency role ``map_file``).

   A tool also can define methods. The name of a method must consist of at least two lower-case
   words separated by ``_``.

   A new tool can be defined by inheriting from one or more other tools.
   When overriding a dependency role, its overriding value must be of the same type as the overridden value
   and it must be at least as restrictive (e.g. if required dependency must not be overridden by a non-required one).
   When overriding an execution parameter, its overriding value must be of the same type as the overridden value.
   When overriding an method, its overriding method must be of the same kind and have the same signature as the
   overridden method.

   Each subclass of :class:`Tool` must be defined in a source code location unique among all subclasses of
   :class:`Tool`. The definition raises :exc:`DefinitionAmbiguityError` if its location cannot be determined or
   if another subclass of :class:`Tool` is defined at the same location.

   Example::

      class Compiler(dlb.ex.Tool):
          WARNINGS = ('all',)
          source_file = dlb.ex.input.RegularFile()
          object_file = dlb.ex.output.RegularFile()
          async def redo(self, result, context): ...

      class Linker(dlb.ex.Tool):
          BE_VERBOSE = False
          object_files = dlb.ex.input.RegularFile[1:]()
          linked_file = dlb.ex.output.RegularFile()
          map_file = dlb.ex.output.RegularFile(required=False)
          async def redo(self, result, context): ...

      compiler = Compiler(source_file='main.cpp', object_file='main.cpp.o')
      linker = Linker(object_files=[compiler.object_file], linked_file='main', BE_VERBOSE=True)

   When a tool instance is constructed, the keyword arguments passed to its constructor define its concrete dependencies
   and the values of its execution parameters.
   Each keyword argument names a dependency role or an execution parameter.

   - When a keyword argument names a *dependency role*, its value defines the concrete dependencies of the
     dependency role. It depends on the dependency role, whether such a definition is *permitted* or even *required*.
     For an *explicit* dependency role, it is required.

   - When a keyword argument names an *execution parameter*, its value defines the value of the execution parameter
     (it overrides the default value defines at declaration of the execution parameter as a class attribute).
     The same restrictions apply as for overriding the execution parameter by subclassing.

   The concrete dependencies passed as keyword arguments to the constructor are validated by the
   tool's dependency roles and made accessible (for reading only) as an attribute with the name of the corresponding
   dependency role and a type determined by the dependency role
   (e.g. :class:`dlb.fs.Path` for :class:`input.RegularFile`)::

      >>> Compiler.object_file       # dependency role
      <dlb.ex.input.RegularFile object at ...>

      >>> Compiler(...).object_file  # concrete dependency
      Path('main.cpp.o')

   The execution parameters passes as keyword arguments to the constructor are made accessible (for reading only)
   as an attribute:

       >>> Linker.BE_VERBOSE
       False  # default value defined in tool class
       >>> Linker(...).BE_VERBOSE  # ... no keyword argument BE_VERBOSE=
       False  # default value defined in tool class

       >>> Linker(BE_VERBOSE=True).BE_VERBOSE
       True   # value from keyword argument in constructor

   .. method:: start(force_redo=False)

      Start running the tool instance in the :term:`active context` and return a result (proxy) object *result*.

      ``bool(result)`` is ``True`` if a :term:`redo` is performed and ``False`` otherwise.
      A redo is performed if *force_redo* is ``True`` or if it is :term:`necessary <redo necessity>`.
      "Performing a redo" means scheduling the eventual (asynchronous) execution of :meth:`redo()` of this
      class.

      If a redo is performed, this method returns while the redo is pending (not complete).
      After each of the following actions the redo is guaranteed to be complete, either successfully or
      by raising an exception:

      - read of a "public" attribute (or method) of the result (proxy) object
      - exit of the context :meth:`start()` was called in
      - enter of an inner context of the context :meth:`start()` was called in
      - modification of :attr:`env <dlb.ex.Context.env>` or :attr:`helper <dlb.ex.Context.helper>` of
        the context :meth:`start()` was called in
      - call of :meth:`start()` of the same tool instance

      The result (proxy) object *result* contains an attribute for every dependency role of the tool which contains the
      concrete dependencies.
      *result* also has a method ``complete()`` which only returns *result*.

      Use ``t.start(...).complete()`` for a tool instance *t* to block until the possible redo is complete.

      If ``bool(result)`` is ``True``, all attributes for dependency roles have an assigned value.
      If ``bool(result)`` is ``False``, only the attributes for explicit dependency roles have an assigned value;
      the value of all attributes for non-explicit dependency roles is ``NotImplemented``.

      :param force_redo: perform a redo even if not necessary?
      :type force_redo: bool
      :return: result (proxy) object

   .. method:: redo(result, context)

      Performs the actual work for this tool instance and creates all its output dependencies
      (output files from input files, for example).

      Override this awaitable method in a subclass to implement a new :class:`Tool` (do not forget ``async``!).

      Assign to attributes of *result* to define a non-explicit concrete dependency for the dependency role with the
      same name.

      For a redo to be successful, this method must perform the following tasks:

      - Create all explicit output dependencies
      - Assign values to each required non-explicit dependencies

      Use :meth:`await context.execute_helper() <RedoContext.execute_helper()>` to call executable files.

      Make sure the :term:`mtime` of each filesystem object that is an output dependency of this tool instance is
      updated when it is (potentially) modified, even if the redo fails.

      For a filesystem object whose path *p* is contained in an output dependency, it is recommended to first write
      to a temporary filesystem object *q* and then replace it with ``context.replace_output(p, q)``.
      This guarantees that no incomplete output dependency is left behind (like an only half-written object file)
      when the :term:`redo` is aborted.
      A filesystem object that is an output dependency is treated as modified by the redo if it is a non-explicit
      dependency or if it is an explicit dependency that was replaced with ``context.replace_output()``.

      Raises :exc:`python:RuntimeError` on the attempt to enter a new :class:`dlb.ex.Context` as a context manager or
      to modify the :term:`active context`.

      Return ``True`` if the next run this :term:`tool instance` should perform a :term:`redo`, regardless of the
      necessity according to its dependencies.

      Example::

         class ATool(dlb.ex.Tool):
             EXECUTABLE = 'atool'

             source_file = dlb.ex.input.RegularFile()
             output_file = dlb.ex.output.RegularFile()
             included_files = dlb.ex.input.RegularFile[:](explicit=False)

             async def redo(self, result, context):
                 if ...:
                     raise ValueException('invalid ...')
                 with context.temporary() as temp_file_
                     await context.execute_helper(self.EXECUTABLE,
                                                  ['-o', temp_file, result.source_file])
                     result.included_files = ...
                     context.replace_output(result.output_file, temp_file)

      :param result: result proxy object to be returned by :meth:`start()`
      :param context: redo context
      :type context: RedoContext
      :return: request a redo for the next run of the tool instance?
      :rtype: None | bool

   .. attribute:: definition_location

      The definition location of the class.

      It is a tuple of the form ``(file_path, in_archive_path, lineno)`` and uniquely identifies the tool
      among all subclasses of :class:`Tool`.

      *in_archive_path* is ``None`` if the class was defined in an existing Python source file and *file_path* is
      the :func:`python:os.path.realpath()` of this file.

      *in_archive_path* is the path relative of the source file in the zip archive, if the class was defined in an
      existing zip archive with a filename ending in :file:`.zip` (loaded by :mod:`python:zipimport`) and *file_path* is
      the :func:`python:os.path.realpath()` of this zip archive.

      *lineno* is the 1-based line number in the source file.

   .. attribute:: fingerprint

      The *permanent local tool instance fingerprint* of this instance.

      This is a :class:`python:bytes` object of fixed size, calculated from all its concrete dependencies *d* with
      ``d.explicit == True`` and all its execution parameters.

      If two instances of the same subclass of :class:`Tool` have equivalent explicit dependencies and equivalent
      execution parameters, their fingerprints are equal.
      Otherwise, their fingerprints are different with very high probability.

      The explicit dependencies of two instances are equivalent, if they are equal or differ only in a way that does
      *not affect the meaning* of the dependencies while the :term:`tool instance` is running.
      Execution parameters are equivalent if they are equal after replacing all mappings by dicts and all
      iterables that are no string, bytes, or sets by tuples.


Redo context
------------

A redo context is a read-only view for a :class:`dlb.ex.Context` with some additional
methods related to :term:`dynamic helpers <dynamic helper>` and dependencies.

.. class:: RedoContext

   A redo context is constructed automatically by :meth:`Tool.start()`. Redo contexts should not be constructed manually.

   .. method:: execute_helper(helper_file, arguments=(), *, cwd=None, expected_returncodes=frozenset([0]), \
               forced_env={}, stdout_output=None, stderr_output=None)

      Execute the *helper_file* with command-line arguments *arguments* in a subprocess with *cwd* as
      its working directory and wait for it to complete.
      The execution is considered successful if and only if its returncode is one in *expected_returncodes*.

      If *cwd* is not ``None``, is must be the path of directory in the :term:`managed tree` or in :file:`.dlbroot/t/`
      of the :term:`management tree`.
      Otherwise the working tree's root is used as the working directory.

      All members of *arguments* are converted to str objects with
      :meth:`prepare_arguments(arguments, cwd=cwd) <prepare_arguments()>`.

      :attr:`env <dlb.ex.Context.env>` of this object, modified by *forced_env*, forms the environment for the
      subprocess.

      .. note::
         On Windows, in order to run a side-by-side assembly the specified *env* must include a valid
         :envvar:`!SYSTEMROOT`.

      The file descriptors 1 (stdout) and 2 (stderr) are open in the subprocess. Their meaning is specified by
      *stdout_output* and *stderr_output*. No other file descriptor from the Python process is open in the subprocess.

      :param helper_file: :term:`dynamic helper` to be executed as a relative path
      :param arguments: command-line arguments
      :type arguments: iterable of objects that can be converted to str
      :param cwd: working directory of the subprocess to be started
      :type cwd: ``None`` or a :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param expected_returncodes: expected return codes of the :term:`dynamic helper` *helper_file*
      :type expected_returncodes: collection of integers
      :param forced_env: dictionary of values to override in :attr:`env <dlb.ex.Context.env>` or ``None``
      :type forced_env: None | Dict[str, str]
      :param stdout_output:
         If ``None``: use :data:`dlb.cf.execute_helper_inherits_files_by_default`.
         If ``True``: inherit stdout of the Python process (the file descriptor, not :data:`sys.stdout`).
         If ``False``: suppress the output.
         Otherwise: the path of the output file as a :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can
         be constructed from (opened with mode ``'wb'``).
      :param stderr_output:
         If ``None``: use :data:`dlb.cf.execute_helper_inherits_files_by_default`.
         If ``True``: inherit stderr of the Python process (the file descriptor, not :data:`sys.stderr`).
         If ``False``: suppress the output.
         Otherwise: the path of the output file as a :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can
         be constructed from (opened with mode ``'wb'``).
      :rtype: int
      :return: return code of the subprocesses (one of *expected_returncodes*)

      :raises HelperExecutionError: if the subprocess exits with a returncode not in *expected_returncodes*.

   .. method:: execute_helper_with_output(helper_file, arguments=(), *, cwd=None, expected_returncodes=frozenset([0]), \
                                          forced_env={}, output_to_process=1, other_output=None, \
                                          chunk_processor=None)

      Execute the *helper_file* with command-line arguments *arguments* in a subprocess with *cwd* as
      its working directory, wait for it to complete, and return its output.

      When *chunk_processor* is ``None``, the entire output of the subprocess to stdout or stderr
      (as defined by *output_to_process*) is returned as ``bytes`` objects.
      Example::

         _, output = await context.execute_helper_with_output(..., output_to_process=2)  # without *chunk_processor*
         # output is a 'bytes' objects containing the output of the subprocess to stderr

      When *chunk_processor* is not ``None``, the output of the subprocess is split into chunks separated by
      the non-empty ``bytes`` object ``chunk_processor.separator``, and ``chunk_processor.process(chunk, is_last)``
      is called for each of the chunks (without ``chunk_processor.separator``) right after they occur.
      *is_last* is ``False`` for every call except the last one that was not delimited by ``chunk_processor.separator``
      but by the end of the stream.
      This is suitable when a subprocess outputs a lot of data (even unbounded) but only a small part of it is
      interesting.
      Example::

         class Processor(dlb.ex.ChunkProcessor):
             separator = b'\r\n'
             max_chunk_size = 100  # maximum chunk size (without separator)

             def __init__(self):
                 self.result = []

             def process(self, chunk: bytes, is_last: bool):  # len(chunk) is <= 100, chunk does not contain '\r\n'
                 if chunk.startswith('hello'):
                     self.result.append(chunk)

          _, output = await context.execute_helper_with_output(..., chunk_processor=Processor())
          # output is a list of 'bytes' objects starting with b'hello'

      The file descriptors 1 (stdout) and 2 (stderr) are open in the subprocess. Their meaning is specified by
      *output_to_process* and *other_output*. No other file descriptor from the Python process is open in the
      subprocess.

      See :meth:`execute_helper()` for a description of *cwd*, *arguments*, *expected_returncodes*, and *forced_env*.

      :param helper_file: :term:`dynamic helper` to be executed as a relative path
      :param arguments: command-line arguments
      :type arguments: iterable of objects that can be converted to str
      :param cwd: working directory of the subprocess to be started
      :type cwd: ``None`` or a :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param expected_returncodes: expected return codes of the :term:`dynamic helper` *helper_file*
      :type expected_returncodes: collection of integers
      :param forced_env: dictionary of values to override in :attr:`env <dlb.ex.Context.env>` or ``None``
      :type forced_env: None | Dict[str, str]
      :type output_to_process: int
      :param output_to_process: 1 to return stdout and 2 to return stderr of the subprocess
      :param other_output:
         Output for stdout of the subprocess if *output_to_process* is 2 and for *stderr* otherwise.
         If ``None``: use :data:`dlb.cf.execute_helper_inherits_files_by_default`.
         If ``True``: inherit stdout/stderr of the Python process
         (the file descriptor, not :data:`sys.stdout`/:data:`sys.stderr`).
         If ``False``: suppress the output.
         Otherwise: the path of the output file as a :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can
         be constructed from (opened with mode ``'wb'``).
      :type chunk_processor: None | dlb.ex.ChunkProcessor
      :param chunk_processor:
         If ``None`` the entire output is returned.
         Otherwise, ``chunk_processor.result`` after each chunk was fed to *chunk_processor* as described above.

      :raises HelperExecutionError: if the subprocess exits with a returncode not in *expected_returncodes*.
      :raises asyncio.LimitOverrunError: if *chunk_processor* is not ``None`` and the subprocess outputs
         more than ``chunk_processor.max_chunk_size`` bytes without a ``chunk_processor.separator``.

      Returns a tuple ``(returncode, output)``. *returncode* is the returncode of the subprocess and *output* its
      output to stdout or stderr --- processed by ``chunk_processor`` if *chunk_processor* is ``None`` ---
      as described above.

   .. method:: prepare_arguments(self, arguments, cwd=None)

      Convert all members of *arguments* to str objects.

      If a member of *arguments* is a :class:`dlb.fs.Path` object *p* with ``p.is_absolute() == ``True``, is is
      replaced by ``str(p.native)``.
      If a member of *arguments* is a :class:`dlb.fs.Path` object *p* with ``p.is_absolute() == ``False``, is is
      replaced by ``str(q.native)``, where *q* is *p* expressed relative to the working directory. It must denote
      a filesystem object in the :term:`managed tree` or in :file:`.dlbroot/t/` of the :term:`management tree`.

      If *cwd* is not ``None``, is must be the path of directory in the :term:`managed tree` or in :file:`.dlbroot/t/`
      of the :term:`management tree`.
      Otherwise the working tree's root is used as the working directory.

      :param arguments: command-line arguments
      :type arguments: iterable of objects that can be converted to str
      :param cwd: working directory of the subprocess to be started
      :type cwd: ``None`` or a :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :return: List of strings

   .. method:: replace_output(path, source)

      Replace the --- existing or non-existent --- filesystem object *path* by *source*.
      *path* must be contained in a dependency of the tool instance.

      *path* and *source* must be different filesystem objects.

      After successful completion, *path* exists and *source* does not exist.
      If the parent directory of *path* does not exist, it is created (with all its parent directories).

      The actual operation depends on the corresponding dependency role.
      If it is :class:`dlb.ex.output.RegularFile(replace_by_same_content=False, ...) <dlb.ex.output.RegularFile>`
      and *path* and *source* both exist with the same content, *path* is not replaced and treated as unchanged.

      If *path* is replaced, this is always done by an atomic operation. If it fails, *path* is either *source*
      afterwards or it does not exist.

      :param path: a path of a future filesystem object in the managed tree
      :type path: :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param source: a path of a filesystem object in the managed tree
      :type source: :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :return: `False` if *path* was not changed by this operation, `True` otherwise.

      :raises ValueError:
         if *path* is not a :term:`managed tree path` contained in an explicit output dependency
      :raises ValueError:
         if *source* is not a :term:`working tree path` of a filesystem object in the :term:`managed tree` or
         in :file:`.dlbroot/t/` of the :term:`management tree` that is different from *path*.


Dependency classes
------------------

A dependency class is a subclass of :class:`Dependency`.
Its instances describe *dependency roles* (as attributes of a :class:`Tool`).

The :meth:`Dependency.validate()` methods of dependency classes are used by :term:`tool instances <tool instance>`
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
       include_search_directories = dlb.ex.input.Directory[1:]()  # a sequence of at least one dlb.ex.input.Directory
       cache_directory = dlb.ex.input.Directory()  # a single dlb.ex.input.Directory

   tool = Tool(include_search_directories=['build/out/Generated/', 'src/Implementation/'])

   # these are concrete dependencies of the tool instance 'tool':
   tool.include_search_directories  # (Path('build/out/Generated/'), Path('src/Implementation/'))
   tool.cache_directory  # (Path('build/out/Generated/'), Path('src/Implementation/'))


Dependency classes are organized in an a hierarchy according to their meaning to a :term:`tool` by the means of the
following abstract classes:

.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.ex.InputDependency" -> "dlb.ex.Dependency";
       "dlb.ex.OutputDependency" -> "dlb.ex.Dependency";
   }

.. class:: InputDependency

   A :class:`Dependency` that describes an input dependency of a tool.

   A running :term:`tool instance` must perform a :term:`redo` if it (e.g. the :term:`mtime` of a file) has changed
   compared to the state before the last known successful redo of the :term:`tool instance`.

   An redo *must not* modify it, successful or not
   (the same object can be an output dependency of the same tool instance though which *can* be modified, although).

.. class:: OutputDependency

   A :class:`Dependency` that describes an output dependency of a tool.

   A successful redo *must* generate it (e.g. create a regular file).


Dependency classes support the following methods and attributes:

.. class:: Dependency(required=True, explicit=True)

   If *required* is ``True``, a concrete dependency of this dependency role will never be ``None``.

   If *explicit* is ``True``, the concrete dependency can and must be fully defined when the :term:`tool instance`
   is created. Otherwise, it cannot and must not be; it is instead automatically assigned by :meth:`Tool.start()`.

   .. param required: is a value other than ``None`` required?
   .. type required: bool
   .. param explicit: explicit dependency?
   .. type explicit: bool

   Each supported constructor argument is available as a property of the same name.

   :raises DependencyError:
      if the arguments of the constructor do not match the declared dependency roles of the class

   .. class:: Value

      A (potentially abstract) class such that ``isinstance(v, Value)`` is ``True`` for each validated single value
      *v* of each instance *t* of this class.

      This is the type of ``t.validate()`` if :attr:`multiplicity <Dependency.multiplicity>` is ``None`` and the type
      of each member of ``t.validate()`` otherwise.

   .. method:: validate(value)

      :param value: The concrete dependency to convert and validate except ``None``
      :type value: Any type the concrete dependency can convert to *T*
      :return: The validated *value* of type *T*

      :raises TypeError: If :attr:`multiplicity` is not ``None`` and *value* is not iterable or is a string

   .. method:: compatible_and_no_less_restrictive(other)

      Is this dependency role an instance of the same class as *other* with a multiplicity and properties no less
      restrictive than the ones of *other*?

      :param other: reference dependency role
      :type other: Dependency
      :rtype: bool

   .. attribute:: multiplicity

      The multiplicity of the dependency role.

      Is ``None`` or an multiplicity object that supports test for (in)equality and membership  of integers
      (:meth:`__eq__ <object.__eq__>` and :meth:`__contains__ <object.__contains__>`, respectively).

   .. method:: tuple_from_value(value)

      Return *value* if :attr:`multiplicity` is ``None`` and a tuple of its members otherwise.

      Example::

         # returns a tuple of t.Value objects or raises an exception:
         >>> v = t.tuple_from_value(t.validate(...))


Each non-abstract dependency class is derived from :class:`InputDependency` or from from :class:`InputDependency`:

.. graphviz::

   digraph foo {
       graph [rankdir=BT];
       node [height=0.25];
       edge [arrowhead=empty];

       "dlb.ex.input.RegularFile" -> "dlb.ex.InputDependency";
       "dlb.ex.input.NonRegularFile" -> "dlb.ex.InputDependency";
       "dlb.ex.input.Directory" -> "dlb.ex.InputDependency";
       "dlb.ex.input.EnvVar" -> "dlb.ex.InputDependency";

       "dlb.ex.output.RegularFile" -> "dlb.ex.OutputDependency";
       "dlb.ex.output.NonRegularFile" -> "dlb.ex.OutputDependency";
       "dlb.ex.output.Directory" -> "dlb.ex.OutputDependency";
       "dlb.ex.output.Object" -> "dlb.ex.OutputDependency";

       "dlb.ex.InputDependency" -> "dlb.ex.Dependency";
       "dlb.ex.OutputDependency" -> "dlb.ex.Dependency";
   }

.. note::

   dlb identifies filesystem objects by their :term:`managed tree path`. It assumes that different managed tree paths
   point to different filesystem objects.

   If a filesystem object serves as an output dependency of one :term:`tool instance` and as an input dependency
   of another: Make sure both dependencies use the same path.
   A :term:`redo miss` could happen otherwise.

   You are always safe without hard links, symbolic links and case-insensitive filesystems.


Input dependency classes
^^^^^^^^^^^^^^^^^^^^^^^^

+-------------------------------------+-----------------------------------------------+----------------------------+
| Dependency class                    | Keyword arguments of constructor              | Depended-upon state        |
|                                     +-----------------------+-----------------------+ for redo necessity         |
|                                     | Name                  | Default value         |                            |
+=====================================+=======================+=======================+============================+
| :class:`input.RegularFile`          | *cls*                 | :class:`dlb.fs.Path`  | summary of status of       |
+-------------------------------------+                       |                       | filesystem object          |
| :class:`input.NonRegularFile`       |                       |                       | with given                 |
+-------------------------------------+                       |                       | :term:`managed tree path`  |
| :class:`input.Directory`            |                       |                       |                            |
+-------------------------------------+-----------------------+-----------------------+----------------------------+
| :class:`input.EnvVar`               | *name*                |                       | value of enviroment        |
|                                     +-----------------------+-----------------------+ variable *name* in         |
|                                     | *pattern*             |                       | active context             |
|                                     +-----------------------+-----------------------+                            |
|                                     | *example*             |                       |                            |
+-------------------------------------+-----------------------+-----------------------+----------------------------+

In addition to the keyword arguments of the specific constructors described here, all constructors also accept the
keyword arguments of the constructor of :class:`Dependency`.


.. class:: input.RegularFile(cls=dlb.fs.Path, required=True, explicit=True)

   A dependency role for regular files, identified by their paths.

   If a path is relative, it is treated as relative to
   :attr:`dlb.ex.Context.active.root_path <dlb.ex.Context.root_path>`, and it must be
   :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>` (if the path does not contain
   :file:`..` components, these requirements are met).

   The :meth:`validated value <Dependency.validate()>` of a concrete dependency is the file's path as an instance
   of *cls* if :attr:`multiplicity <Dependency.multiplicity>` is ``None`` and a tuple of the file's paths
   otherwise.

   The depended-upon state for redo necessity is a summary of each file's status which consists in

   - :term:`mtime`
   - size
   - UID
   - GID
   - filesystem permissions

   For a file outside the :term:`managed tree`, the state is always assumed to remain unchanged between
   :term:`runs of dlb <run of dlb>`.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    source_files = dlb.ex.input.RegularFile[1:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(source_files=['src/main.cpp'])
      >>> tool.source_files
      (NoSpacePath('src/main.cpp'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: input.NonRegularFile(cls=dlb.fs.Path, required=True, explicit=True)

   A dependency role for filesystem objects that are neither directories nor regular files, identified by their paths.

   If a path is relative, it is treated as relative to
   :attr:`dlb.ex.Context.active.root_path <dlb.ex.Context.root_path>`, and it must be
   :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>` (if the path does not contain
   :file:`..` components, these requirements are met).

   The :meth:`validated value <Dependency.validate()>` of a concrete dependency is each file's path as an instance
   of *cls* if :attr:`multiplicity <Dependency.multiplicity>` is ``None`` and a tuple of the file's paths
   otherwise.

   The depended-upon state for redo necessity is a summary of each file's status which consists in

   - :term:`mtime`
   - size
   - type of filesystem object (e.g. symbolic link, block device, ...)
   - target path if a symbolic link
   - UID
   - GID
   - filesystem permissions

   For a file outside the :term:`managed tree`, the state is always assumed to remain unchanged between
   :term:`runs of dlb <run of dlb>`.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    symbolic_links = dlb.ex.input.NonRegularFile[:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(symbolic_links=['src/current'])
      >>> tool.symbolic_links
      (NoSpacePath('src/current'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: input.Directory(cls=dlb.fs.Path, required=True, explicit=True)

   A dependency role for directories, identified by their paths.

   If a path is relative, it is treated as relative to
   :attr:`dlb.ex.Context.active.root_path <dlb.ex.Context.root_path>`, and it must be
   :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>` (if the path does not contain
   :file:`..` components, these requirements are met).

   The :meth:`validated value <Dependency.validate()>` of a concrete dependency is the directory's path as an
   instance of *cls* if :attr:`multiplicity <Dependency.multiplicity>` is ``None`` and a tuple of the
   directory's paths otherwise.

   The depended-upon state for redo necessity is a summary of each directory's status which consists in

   - :term:`mtime`
   - size
   - UID
   - GID
   - filesystem permissions

   For a directory outside the :term:`managed tree`, the state is always assumed to remain unchanged between
   :term:`runs of dlb <run of dlb>`.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    cache_directory = dlb.ex.input.Directory(required=False)
      >>> tool = Tool(cache_directory='/tmp/')
      >>> tool.cache_directory
      Path('tmp/')

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: input.EnvVar(name, pattern, example, required=True, explicit=True)

   A dependency role for an environment variable named *name*.
   It must not have a multiplicity (other than ``None``).

   If *explicit* is ``True``, the value assigned in the constructor of the :term:`tool instance` is used for all
   future runs of the tool instance.
   Otherwise, the current value of the :term:`active context` is used each time :meth:`Tool.start()` is called.

   The value of the environment variable is valid if it is a string that matches the regular expression *pattern*
   or if it is ``None`` and *required* is ``False``.

   The :meth:`validated value <Dependency.validate()>` of a concrete dependency is a :class:`Value` instance
   with the environment variable's name and value.

   The depended-upon state for redo necessity is the value of environment variable *name* in the :term:`active context`.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>     language_code = dlb.ex.input.EnvVar(
      >>>                         name='LANG',
      >>>                         pattern=r'(?P<language>[a-z]{2})_(?P<territory>[A-Z]{2})',
      >>>                         example='sv_SE')
      >>>     cflags_string = dlb.ex.input.EnvVar(name='CFLAGS', pattern=r'.+', example='-Wall')
      >>> tool = Tool(language_code='de_CH')  # use 'de_CH' as value of the environment variable for all
      >>> tool.language_code.groups['territory']
      'CH'
      >>> tool.cflags_string
      NotImplemented
      >>> tool.start().cflags_string.raw  # assuming dlb.ex.Context.active.env['CFLAGS'] of '-O2'
      '-O2'

   :param pattern: validation pattern for value as a regular expression
   :type pattern: str | :class:`python:typing.Pattern`
   :param example: typical value of an environment variable, *pattern* must match this
   :type example: str

   .. class:: Value

      A class decorated with :func:`python:dataclasses.dataclass` and the following fields:

      .. attribute:: name

         The name of the environment variable, as in the corresponding concrete dependency.

      .. attribute:: raw

         The value of the environment variable.

      .. attribute:: groups

         The named groups of *pattern* of the corresponding concrete dependency when matched against *raw*.


Output dependency classes
^^^^^^^^^^^^^^^^^^^^^^^^^

+-------------------------------------+--------------------------------------------------------+
| Dependency class                    | Keyword arguments of constructor                       |
|                                     +---------------------------+----------------------------+
|                                     | Name                      | Default value              |
+=====================================+===========================+============================+
| :class:`output.RegularFile`         | *cls*                     | :class:`dlb.fs.Path`       |
+                                     +---------------------------+----------------------------+
|                                     | *replace_by_same_content* | ``True``                   |
+-------------------------------------+---------------------------+----------------------------+
| :class:`output.NonRegularFile`      | *cls*                     | :class:`dlb.fs.Path`       |
+-------------------------------------+---------------------------+----------------------------+
| :class:`output.Directory`           | *cls*                     | :class:`dlb.fs.Path`       |
+-------------------------------------+---------------------------+----------------------------+
| :class:`output.Object`              |                           |                            |
+-------------------------------------+---------------------------+----------------------------+

In addition to the keyword arguments of the specific constructors described here, all constructors also accept the
keyword arguments of the constructor of :class:`Dependency`.


.. class:: output.RegularFile(cls=dlb.fs.Path, replace_by_same_content=True, required=True, explicit=True)

   A dependency role for regular files in the :term:`managed tree`, identified by their paths.

   If a path is relative, it is treated as relative to
   :attr:`dlb.ex.Context.active.root_path <dlb.ex.Context.root_path>`, and it must be
   :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>` (if the path does not contain
   :file:`..` components, these requirements are met).

   The :meth:`validated value <Dependency.validate()>` of a concrete dependency is the file's path as an instance
   of *cls* if :attr:`multiplicity <Dependency.multiplicity>` is ``None`` and a tuple of the file's paths
   otherwise.

   If *replace_by_same_content* is ``False`` for a dependency role containing *p*, ``context.replace_output(p, q)``
   in :meth:`redo(..., context) <dlb.ex.Tool.redo()>` does not replace *p* if *p* and *q* both exist as accessible
   regular files and have the same content.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    object_file = dlb.ex.output.RegularFile(cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(object_file=['main.cpp.o'])
      >>> tool.object_file
      (NoSpacePath('main.cpp.o'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: output.NonRegularFile(cls=dlb.fs.Path, required=True, explicit=True)

   A dependency role for filesystem objects in the :term:`managed tree` that are neither directories nor regular files,
   identified by their paths.

   If a path is relative, it is treated as relative to
   :attr:`dlb.ex.Context.active.root_path <dlb.ex.Context.root_path>`, and it must be
   :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>` (if the path does not contain
   :file:`..` components, these requirements are met).

   The :meth:`validated value <Dependency.validate()>` of a concrete dependency is the file's path as an instance
   of *cls* if :attr:`multiplicity <Dependency.multiplicity>` is ``None`` and a tuple of the file's paths
   otherwise.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    symbolic_links = dlb.ex.output.NonRegularFile[:](cls=dlb.fs.NoSpacePath)
      >>> tool = Tool(symbolic_links=['dist'])
      >>> tool.symbolic_links
      (NoSpacePath('src/current'),)

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: output.Directory(cls=dlb.fs.Path, required=True, explicit=True)

   A dependency role for directories in the :term:`managed tree`, identified by their paths.

   If a path is relative, it is treated as relative to
   :attr:`dlb.ex.Context.active.root_path <dlb.ex.Context.root_path>`, and it must be
   :term:`collapsable <collapsable path>` and :term:`non-upwards <non-upwards path>` (if the path does not contain
   :file:`..` components, these requirements are met).

   The :meth:`validated value <Dependency.validate()>` of a concrete dependency is the directory's path as an
   instance of *cls* if :attr:`multiplicity <Dependency.multiplicity>` is ``None`` and a tuple of the
   directory's paths otherwise.

   Example::

      >>> class Tool(dlb.ex.Tool):
      >>>    html_root_directory = dlb.ex.output.Directory(required=False)
      >>> tool = Tool(html_root_directory='html/')
      >>> tool.html_root_directory
      Path('html/')

   :param cls: class to be used to represent the path
   :type cls: dlb.fs.Path

   .. class:: Value

      Is :class:`dlb.fs.Path`.

.. class:: output.Object(required=True, explicit=True)

   A dependency role for any Python object other than ``None`` and ``NotImplemented``.
   *explicit* must be ``False``.

   The :meth:`validated value <Dependency.validate()>` of a concrete dependency is a
   :func:`deep copy <python:copy.deepcopy()>` of the value.

   .. class:: Value

      Is :data:`python:typing.Any`.


Exceptions
----------

.. exception:: NotRunningError

   Raised, when an action requires an :term:`active context` while :term:`dlb was not running <run of dlb>`.

.. exception:: NoWorkingTreeError

   Raised, when the working directory of the calling process is not a :term:`working tree`'s root.

.. exception:: ManagementTreeError

   Raised, when an attempt to prepare or access the :term:`management tree` failed.

.. exception:: ContextNestingError

   Raised, when some contexts were not properly nested.
   I.e. the calls of :meth:`__exit__ <object.__exit__>` did not occur in the opposite order of the corresponding calls
   of :meth:`__enter__ <object.__enter__>`.

.. exception:: WorkingTreeTimeError

   Raised, when the :term:`working tree time` behaved unexpectedly.

.. exception:: ContextModificationError

   Raised, when the modification of an
   :ref:`environment variable dictionary object <dlb-ex-environment-variable-dictionary-objects>` or a
   helper dictionary object has been attempted while its associated :term:`context` is not the :term:`active context`.

.. exception:: WorkingTreePathError

   Raised, when a path is not a :term:`working tree path` with certain properties where it should be.

.. exception:: DefinitionAmbiguityError

   Raised at the definition of a subclass of :class:`Tool`, when the location is unknown or another subclass of
   :class:`Tool` is defined at the same location.

.. exception:: DependencyError

   Raised, when a running :term:`tool instance` has detected a problem with its dependencies before a :term:`redo`.

.. exception:: ExecutionParameterError

   Raised, when a running :term:`tool instance` has detected a problem with its execution parameters before
   a :term:`redo`.

.. exception:: RedoError

   Raised, when a running :term:`tool instance` has detected a problem with its dependencies during or after
   a :term:`redo`.

.. exception:: HelperExecutionError

   Raised, when the execution of a :term:`dynamic helper` file failed.
