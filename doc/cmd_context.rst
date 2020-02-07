:class:`dlb.ex.Context` --- Execution context for tool instances
=================================================================
.. module:: dlb.ex
   :synopsis: Execution context for tool instances

An :term:`(execution) context <context>` describes how running :term:`tool instances <tool instance>` shall interact
with the execution environment outside the :term:`working tree` and with each other.
E.g:

 - number of asynchronously running :term:`tool instances <tool instance>`
 - search paths for :term:`dynamic helper` files

It also controls how diagnostic messages are handled and helps with filesystem abstraction
(e.g. :term:`working tree time`, case sensitivity of names in the :term:`working tree`).

A context is represented as an instance of :class:`dlb.ex.Context` used as a context manager.
The context is entered with the call of :meth:`_enter__` and exit with the return of :meth:`__exit__`.


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


.. class:: Context(path_cls=dlb.fs.Path)

   An instance does nothing unless used as a :term:`python:context manager`.

   When used as a context manager, it embodies an (execution) context and :term:`activates <active context>` it:

      a. a :term:`root context`, if :term:`dlb is not yet running <run of dlb>`;

      b. an inner context of the current :term:`active context`, otherwise.

   When a root context is entered, the working directory of the Python process must be a :term:`working tree`'s root,
   which contains a directory :file:`.dlbroot`, that is not a symbolic link.

   When a context (root or not) is entered, the path of the :term:`working tree`'s root must be representable as
   as ``path_cls``. This allows you to impose :ref:`restrictions <restricting_paths>` on the accepted paths.

   :param path_cls: the subclass of :class:`dlb.fs.Path` to be used to represent the :term:`working tree`'s root
   :type path_cls: dlb.fs.Path
   :raises TypeError: if ``path_cls`` is not a subclass of :class:`dlb.fs.Path`

   Entering or exiting a context may raise the following exceptions:

   +---------------------------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | exception                                   | meaning                                                                     | when                           |
   +=============================================+=============================================================================+================================+
   | :exc:`.dlb.ex.context.NoWorkingTreeError`   | the working directory is not a :term:`working tree`'s root                  | entering :term:`root context`  |
   +---------------------------------------------+-----------------------------------------------------------------------------+                                |
   | :exc:`.dlb.ex.context.ManagementTreeError`  | the :term:`management tree` cannot be setup inside the :term:`working tree` |                                |
   +---------------------------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | :exc:`ValueError`                           | the :term:`working tree`'s root path violates the requested restrictions    | entering (any) context         |
   +---------------------------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | :exc:`.dlb.ex.context.NestingError`         | the contexts are not properly nested                                        | exiting (any) context          |
   +---------------------------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | :exc:`.dlb.ex.context.WorkingTreeTimeError` | :term:`working tree time` behaved unexpectedly                              | exiting :term:`root context`   |
   +---------------------------------------------+-----------------------------------------------------------------------------+--------------------------------+

   .. note::
      Most attributes and methods are available "on the class" as well as "on the instance", and refer to the
      corresponding attribute of the :term:`root context`::

       with dlb.ex.Context:
           with dlb.ex.Context as c:
               ... = dlb.ex.Context.working_tree_time_ns   # preferred
               ... c.root.working_tree_time_ns             # also possible
               ... c.working_tree_time_ns                  # also possible

   The :class:`dlb.ex.Context` class supports the following methods and attributes:

   .. attribute:: root

      The current :term:`root context`.

      Same on class and instance.

      :raises .dlb.ex.context.NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: active

      The current :term:`active context`.

      Same on class and instance.

      :raises .dlb.ex.context.NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: path_cls

      The subclass of :class:`.dlb.fs.Path` defined in the constructor.

      When called on class, it refers to the :term:`root context`.

      :raises .dlb.ex.context.NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: root_path

      The absolute path to the :term:`working tree`'s root.

      It is an instance of ``dlb.ex.Context.root.path_cls`` and
      is representable as an instance of ``path_cls`` of the :term:`active context` and every possible outer context.

      Same on class and instance.

      :raises .dlb.ex.context.NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: working_tree_time_ns

      The current :term:`working tree time` in nanoseconds as an integer.

      Same on class and instance.

      :raises .dlb.ex.context.NotRunningError: if :term:`dlb is not running <run of dlb>`).

   .. method:: create_temporary(self, suffix='', prefix='t', is_dir=False)

      Creates a temporary regular file (for ``is_dir`` = ``False``) or a temporary directory (for ``is_dir`` = ``True``)
      in the :term:`management tree` and returns is absolute path.

      The file name will end with ``suffix`` (without an added dot) and begin with ``prefix``.

      ``prefix`` must not be empty.
      ``prefix`` and ``suffix`` must not contain an path separator.

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
         The number of file name candidates tried for a given combination of ``prefix`` and ``suffix`` is limited by an
         OS-dependent number. A best practise is therefore to remove the created regular file or directory manually
         after use, although they are removed automatically when the :term:`root context` is exit.

      :param suffix: suffix of the file name of the path
      :type suffix: str

      :param prefix: prefix of the file name of the path
      :type prefix: str

      :type is_dir: bool

      :return: an instance ``p`` of :attr:`.dlb.ex.Context.path_cls` of with ``p.is_dir() = is_dir``.
      :rtype: :class:`.dlb.fs.Path`

      :raises ValueError:
         if ``prefix`` is empty or the resulting path is not representable as a :attr:`.dlb.ex.Context.path_cls`
      :raises FileExistsError: if all tried candidates already existed

      :raises .dlb.ex.context.NotRunningError: if :term:`dlb is not running <run of dlb>`).
