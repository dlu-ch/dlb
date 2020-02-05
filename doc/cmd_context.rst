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

   with dlb.ex.Context():        # root context
       with dlb.ex.Context():
           ...
       with dlb.ex.Context():
           ...


.. class:: Context

   An instance does nothing unless used as a :term:`python:context manager`.

   When used as a context manager, it embodies an (execution) context and :term:`activates <active context>` it:

      a. a :term:`root context`, if :term:`dlb is not yet running <run of dlb>`;

      b. an inner context of the current :term:`active context`, otherwise.

   When a root context is entered, the working directory of the Python process must be a :term:`working tree`'s root,
   which contains a directory :file:`.dlbroot`, that is not a symbolic link.

   Entering or exiting a context may raise the following exceptions:

   +-------------------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | exception                           | meaning                                                                     | when                           |
   +=====================================+=============================================================================+================================+
   | :exc:`context.NoWorkingTreeError`   | the working directory is not a :term:`working tree`'s root                  | entering :term:`root context`  |
   +-------------------------------------+-----------------------------------------------------------------------------+                                |
   | :exc:`context.ManagementTreeError`  | the :term:`management tree` cannot be setup inside the :term:`working tree` |                                |
   +-------------------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | :exc:`context.NestingError`         | the contexts are not properly nested                                        | exiting (any) context          |
   +-------------------------------------+-----------------------------------------------------------------------------+--------------------------------+
   | :exc:`context.WorkingTreeTimeError` | :term:`working tree time` behaved unexpectedly                              | exiting :term:`root context`   |
   +-------------------------------------+-----------------------------------------------------------------------------+--------------------------------+

   .. note::
      Most attributes and methods are available "on the class" as well as "on the instance", and refer to the
      corresponding attribute of the :term:`root context`::

       with dlb.ex.Context:
           with dlb.ex.Context as c:
               ... = dlb.ex.Context.working_tree_time_ns   # preferred
               ... c.root.working_tree_time_ns             # also possible
               ... c.working_tree_time_ns                  # also possible


   .. attribute:: root

      The current :term:`root context`.

      :raises dlb.ex.context.NotRunning: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: active

      The current :term:`active context`.

      :raises dlb.ex.context.NotRunning: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: root_path

      The absolute path to the :term:`working tree`'s root.

      Same on class and instance.

      :raises dlb.ex.context.NotRunning: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: working_tree_time_ns

      The current :term:`working tree time` in nanoseconds as an integer.

      Same on class and instance.

      :raises dlb.ex.context.NotRunning: if :term:`dlb is not running <run of dlb>`).

   .. attribute:: temporary_path

      The absolute path to the temporary directory, located in the :term:`management tree`.

      Same on class and instance.

      The temporary directory is guaranteed to created as an empty directory when the :term:`root context` is
      entered. Its is removed (with all its content) when the  :term:`root context` is exit.

      Use the temporary directory to store intermediate filesystem objects meant to replace filesystem objects
      in the :term:`managed tree` eventually. This guarantees a correct :term:`mtime` of the target
      (provided, the assumption :ref:`A-F1 <assumption-f1>` holds).

      :raises dlb.ex.context.NotRunning: if :term:`dlb is not running <run of dlb>`).
