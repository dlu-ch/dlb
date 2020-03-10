:mod:`dlb.ex.context` --- Execution contexts
============================================

.. module:: dlb.ex.context
   :synopsis: Execution of tool instances

.. note::

   The entire documented content of this module is also available in :mod:`dlb.ex`.
   For example, :class:`dlb.ex.context.Context` is also available by :class:`dlb.ex.Context <dlb.ex.context.Context>`.
   The use of the latter is recommended.


An :term:`(execution) context <context>` describes how running :term:`tool instances <tool instance>` shall interact
with the execution environment outside the :term:`working tree` and with each other.
E.g:

 - number of asynchronously running :term:`tool instances <tool instance>`
 - search paths for :term:`dynamic helper` files
 - environment variables to be imported from :data:`python:os.environ` for use in :term:`tool instances <tool instance>`

It also controls how diagnostic messages of :term:`tool instances <tool instance>` are handled and helps with filesystem
abstraction (e.g. :term:`working tree time`, case sensitivity of names in the :term:`working tree`).

A context is represented as an instance of :class:`dlb.ex.Context <dlb.ex.context.Context>` used as a context manager.
The context is entered with the call of :meth:`_enter__` and exited with the return of :meth:`__exit__`.

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


Context objects
---------------

.. class:: Context(path_cls=dlb.fs.Path, max_parallel_redo_count=1, find_helpers=False)

   An instance does nothing unless used as a :term:`python:context manager`.

   When used as a context manager, it embodies an (execution) context and :term:`activates <active context>` it:

      a. a :term:`root context`, if :term:`dlb is not yet running <run of dlb>`;

      b. an inner context of the :term:`active context`, otherwise.

   When a root context is entered, the working directory of the Python process must be a :term:`working tree`'s root
   whose absolute path does not contain unresolved symbolic link.

   When a context (root or not) is entered, the path of the :term:`working tree`'s root must be representable as
   as *path_cls*. This allows you to impose :ref:`restrictions <restricting_paths>` on the accepted paths.

   :param path_cls: the subclass of :class:`dlb.fs.Path` to be used to represent the :term:`working tree`'s root
   :type path_cls: dlb.fs.Path
   :param max_parallel_redo_count: maximum number of redos started in this context than can be pending at the same time
   :type max_parallel_redo_count: int
   :param find_helpers:
      if this is ``True``, dynamic helpers not defined explictly are searched for in :attr:`binary_search_paths`
   :param find_helpers: bool
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
   +------------------------------+-----------------------------------------------------------------------------+-------------------------------+

   .. note::
      Most attributes and methods are available "on the class" as well as "on the instance", and refer to the
      corresponding attribute of the :term:`active context`::

       with dlb.ex.Context:
           with dlb.ex.Context as c:
               ... = dlb.ex.Context.working_tree_time_ns   # preferred
               ... c.active.working_tree_time_ns           # also possible
               ... c.working_tree_time_ns                  # also possible

   The :class:`Context` class supports the following methods and attributes:

   .. attribute:: active

      The :term:`active context`.

      Same on class and instance.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: path_cls

      The subclass of :class:`.dlb.fs.Path` defined in the constructor.

      When called on class, it refers to the :term:`active context`.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: max_parallel_redo_count

      The maximum number of redos started in this context than can be pending at the same time, as defined in the
      constructor.

      When called on class, it refers to the :term:`active context`.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: find_helpers

      Find dynamic helpers not defined explictly are in :attr:`binary_search_paths`?
      This is defined defined in the constructor.

      When called on class, it refers to the :term:`active context`.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: root_path

      The absolute path to the :term:`working tree`'s root.

      It is an instance of :attr:`Context.active.path_cls <Context.path_cls>` and
      is representable as an instance of :attr:`path_cls <Context.path_cls>` of the :term:`active context` and every
      possible outer context.

      Same on class and instance.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: binary_search_paths

      A duplicate-free tuple of absolute directory paths where this process should look for binaries according to
      the operating system.

      It is compiled from the members :func:`python:os.get_exec_path()` when the root context is entered.

      Same on class and instance.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. method:: find_path_in(path, search_prefixes=None)

      Find the first existing and accessible *path* in *search_prefixes* and return its absolute path.
      Returns ``None`` if *path* is not found in *search_prefixed*.

      If *path* is a :class:`dlb.fs.Path` with ``path.is_dir()`` = ``True``, existing non-directories in
      *search_prefixes* are ignored.
      If *path* is a :class:`dlb.fs.Path` with ``path.is_dir()`` = ``False``, existing directories in
      *search_prefixes* are ignored.

      Relative paths in *search_prefixes* are treated as relative to :attr:`root_path`.

      If *search_prefixes* is ``None``, :attr:`binary_search_paths` is used instead.

      Does not raise :exc:`OSError`.

      :param path: the relative path to find
      :type path: :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param search_prefixes: paths of directories to search in
      :type search_prefixes: an iterable other than :class:`python:str` or :class:`python:bytes` or ``None``
      :return: an absolute path or ``None``.

   .. attribute:: working_tree_time_ns

      The current :term:`working tree time` in nanoseconds as an integer.

      Same on class and instance.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. method:: create_temporary(self, suffix='', prefix='t', is_dir=False)

      Create a temporary regular file (for *is_dir* = ``False``) or a temporary directory (for *is_dir* = ``True``)
      in the :term:`management tree` and return is absolute path.

      The file name will end with *suffix* (without an added dot) and begin with *prefix*.

      *prefix* must not be empty.
      *prefix* and *suffix* must not contain an path separator.

      Permissions:

       - A created regular file is readable and writable only by the creating user ID.
         If the platform uses permission bits to indicate whether a file is executable, the file is executable by
         no one.

       - A created directory is readable, writable, and searchable only by the creating user ID.

      Same on class and instance.

      .. note::
         Use the temporary directory to store intermediate filesystem objects meant to replace filesystem objects
         in the :term:`managed tree` eventually. This guarantees a correct :term:`mtime` of the target
         (provided, the assumption :ref:`A-F1 <assumption-f1>` holds).

      .. note::
         The number of file name candidates tried for a given combination of *prefix* and *suffix* is limited by an
         OS-dependent number. A best practise is therefore to remove the created regular file or directory manually
         after use, although they are removed automatically when the :term:`root context` is exited.

      :param suffix: suffix of the file name of the path
      :type suffix: str

      :param prefix: prefix of the file name of the path
      :type prefix: str

      :type is_dir: bool

      :return: an :class:`dlb.fs.Path` *p* with ``p.is_dir() = is_dir``
      :rtype: :class:`dlb.fs.Path`

      :raises ValueError: if *prefix* is empty or the resulting path is not representable as a :class:`dlb.fs.Path`
      :raises FileExistsError: if all tried candidates already existed
      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. method:: working_tree_path_of(path, *, is_dir=None, existing=False, collapsable=False,
                                    allow_nontemporary_management=False, allow_temporary=False)

      Return the :term:`managed tree path` of the *path* of a filesystem object in the :term:`managed tree`.

      For *path* to be considered as the path of a filesystem object in the :term:`managed tree`, *path* must either
      be a relative path or it must have :attr:`root_path` as a prefix.

      The arguments *existing* and *collapsable* describe the assuptions on the filesystem content that may be used to
      increase the speed and reduce the number of filesystem accesses.

      If *existing* and *collapsable* are ``True`` and *path* is relative, the filesystem is never accessed.

      If *existing* is ``False``, :meth:`is_dir() <dlb.fs.Path.is_dir()>` of the returned path reflects the type
      of the actual filesystem object. Raises :exc:`dlb.fs.PathNormalizationError` if *path* does not exist.

      If *allow_nontemporary_management* is ``True``, the resulting path may denote a filesystem object in
      the :term:`management tree` except in :file:`.dlbroot/t`.
      If *allow_temporary* is ``True``, the resulting path may denote a filesystem object in :file:`.dlbroot/t`
      of the :term:`management tree`.

      Does *not* raise :exc:`OSError`.

      Same on class and instance.

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
      :rtype: same class as *path* if *path* is a :class:`dlb.fs.Path` and :class:`dlb.fs.Path` otherwise

      :raises dlb.fs.PathNormalizationError:
          if *path* does not exist in the parts of the :term:`working tree` that are described by
          *allow_nontemporary_management* and *allow_temporary*
      :raises ValueError: if the resulting path is not representable
      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: env

      The :ref:`environment variable dictionary object <environment_variable_dictionary_objects>` with
      this context as its associated :term:`context`.

      When called on class, it refers to the :term:`active context`.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: helper

      The dynamic helper dictionary object with this context as its associated :term:`context`.

      The dynamic helper dictionary object maps :term:`dynamic helpers <dynamic helper>` to absolute paths, either
      explicitly or implicitly with the help of :meth:`find_path_in()`.

      If the :term:`active context` and the :term:`root context` both have :attr:`find_helpers` = ``False``
      and no paths was explicitly assigned to the dynamic helper *p* in the active contect or one of its outer contexts,
      a look-up with ``dlb.ex.Context.helper[p]`` performs a search with ``dlb.ex.Context.find_path_in(p)``.
      (Each such search is performed only once for a given path; the result is stored.)

      Examples::

         >>> dlb.ex.Context.helper['gcc']
         Path('/usr/bin/gcc')

         >>> dlb.ex.Context.helper['gcc'] = '/usr/local/bin/my-very-own-very-special-gcc'  # set the path explictly
         >>> dlb.ex.Context.helper['gcc']
         Path('/usr/local/bin/my-very-own-very-special-gcc')

         >>> dlb.ex.Context.helper['tmp/'] = 'out/t/'  # relative path: relative to the working tree's root path
         >>> dlb.ex.Context.helper['tmp/']
         Path('/home/schmutzli/projects/esel/out/t')   # with '/home/schmutzli/projects/esel' as the working tree's root

      When called on class, it refers to the :term:`active context`.

      :raises NotRunningError: if :term:`dlb is not running <run of dlb>`).


.. _environment_variable_dictionary_objects:

Environment variable dictionary objects
---------------------------------------

The environment variable dictionary object *env* returned by :attr:`c.env <Context.env>` for a :term:`context` *c*
is a dictionary-like object of all environment variables defined in this *c*.
*c* is called the associated :term:`context` of *env*.

In addition, the environment variable dictionary object manages the import of environment variables from
environment variables of the outer :term:`context` and restriction of imported or assigned values in the
form of regular expressions.

The environment variables of the outer :term:`context` of the :term:`root context` is defined
by :data:`python:os.environ`.

Example::

    # os.environ usually contains the environment variables in the shell that called the Python interpreter

    with dlb.ex.Context():  # takes a snapshot of os.environ

        # import the environment variable 'LANG' into the context
        dlb.ex.Context.active.env.import_from_outer(
            'LANG', restriction=r'[a-z]{2}_[A-Z]{2}', example='sv_SE')

        # now the environment variable is either undefined or matches the regular expression given
        # (in this context and all future inner contexts)

        ... = dlb.ex.Context.active.env['LANG']
            # value in snapshot of os.environ complying to the restriction or KeyError

        dlb.ex.Context.active.env['LANG'] = 'de_AT'

        with dlb.ex.Context():

            # further restrict the value and make sure it is defined
            dlb.ex.Context.active.env.import_from_outer(
                'LANG', restriction='(?P<language>de).*', example='de_CH')

            ... = dlb.ex.Context.active.env['LANG']  # 'de_AT'
            del dlb.ex.Context.active.env['LANG']

            dlb.ex.Context.active.env['LANG'] = 'de_CH'
            # dlb.ex.Context.active.env['LANG'] = 'fr_FR'  # would raise ValueError

        ... = dlb.ex.Context.active.env['LANG']  # 'de_AT'

        del dlb.ex.Context.active.env['LANG']  # undefine 'LANG'
        dlb.ex.Context.active.env['LANG'] = 'fr_FR'  # ok

Environment variable dictionary object support the following methods and attributes:

.. method:: EnvVarDict.import_from_outer(name, restriction, value_if_undefined=None, example=None)

   Sets the value of the environment variable named *name* from the innermost outer :term:`context` that
   defines it. If no outer :term:`context` defines it, the environment variable remains undefined.

   Also sets the importing restriction for the value of the environment variable; when it is or later becomes
   defined, it regular expression *restriction* must match its value.

   The possible imported value and the importing restriction apply to the context and all its future inner contexts.

   When called for a root contest, the environment variables are imported from :data:`python:os.environ` at the time
   is was entered.

   :param name: (non-empty) name of the environment variable
   :type name: str
   :param restriction: regular expression
   :type restriction: str | :class:`python:typing.Pattern`
   :param example: typical value of a environment variable, *restriction* must match this
   :type example: str

   :raises ValueError:
      if an environment variable named *name* is defined in the associated or an outer :term:`context`
      and *restriction* does not match its value
   :raises NonActiveContextAccessError: if the associated context is not an :term:`active context`

.. method:: EnvVarDict.is_imported(name)

   Returns ``True`` if *name* is the name of an environment variable imported in the associated :term:`context`
   or any of its outer contexts, else `False`.

   :param name: non-empty name of an environment variable
   :type name: str

   :raises TypeError: if *name* is not a string
   :raises ValueError: if *name* is an empty string

.. method:: EnvVarDict.get(name, default=None)

   Return its value if *name* is the name of a defined environment variable in the associated :term:`context`,
   else *default*.

   :param name: non-empty name of an environment variable
   :type name: str

   :raises TypeError: if *name* is not a string
   :raises ValueError: if *name* is an empty string

.. method:: EnvVarDict.items()

   Returns a new view of the dictionary’s items (name, value) pairs of all defined environment variables.

.. describe:: name in env

   Returns `True` if there is a environment variable named *name* defined in *env*, else `False`.

.. describe:: name not in env

   Equivalent to ``not name in env``

.. describe:: env[name] = value

   Defines an imported environment variable named *name* with value *value* in the associated :term:`context` and
   all its future inner contexts.

   Raises :exc:`KeyError`, if *name* was not imported in the associated  :term:`context` or one of its outer contexts.

   Raises :exc:`ValueError`, if *name* was imported in the associated :term:`context` or one of its outer contexts,
   but is invalid with respect to the restriction an importing context (can be this context and any outer context).

   Raises :exc:`NonActiveContextAccessError`, if the associated context is not an :term:`active context`.

.. describe:: del env[name]

   Undefines a defined environment variable named *name* in the associated :term:`context` and all its future
   inner contexts.

   Raises :exc:`KeyError`, if *name* is not defined in the :term:`context`.

   Raises :exc:`NonActiveContextAccessError`, if the associated context is not an :term:`active context`.


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
   I.e. the calls of :meth:`__exit__` did not occur in the opposite order of the corresponding calls of
   :meth:`__enter__`.

.. exception:: WorkingTreeTimeError

   Raised, when the :term:`working tree time` behaved unexpectedly.

.. exception:: ContextModificationError

   Raised, when an :ref:`environment variable dictionary object <environment_variable_dictionary_objects>` or
   a helper dictionaly object is modified while its associated :term:`context` is not the :term:`active context`.

.. exception:: WorkingTreePathError

   Raised, when a path is not a :term:`working tree path` with certain properties where it should be.
