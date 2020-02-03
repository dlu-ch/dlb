:class:`dlb.cmd.Context` --- Execution context for tool instances
=================================================================
.. module:: dlb.cmd
   :synopsis: Execution context for tool instances

The (execution) context describes ???

 - number of asynchronously running :term:`tool instances <tool instance>`
 - search paths for :term:`dynamic helper` files
 - control of diagnostic messages
 - abstraction of :term`management tree`

Contexts can be nested::

   import dlb.cmd

   with dlb.cmd.Context():        # root context
       with dlb.cmd.Context():
           ...
       with dlb.cmd.Context():
           ...


.. class:: Context

   An instance does nothing unless used as a :term:`python:context manager`.

   When used as a context manager, it defines an (execution) context :term:`activates <active context>` it.

   If a `dlb is already running <run of dlb>` it defines an inner context of the current :term:`active context`.
   Otherwise if defines a :term`root context` (which by definition means :term:`dlb is running <run of dlb>`).

   .. attribute:: root

      The current :term:`root context`.

      :raises dlb.cmd.context.NoneActive:
         if there is no root context because :term:`dlb is not running <run of dlb>`).

   .. attribute:: active

      The current :term:`active context`.

      :raises dlb.cmd.context.NoneActive:
         if there is no :term:`active context` because :term:`dlb is not running <run of dlb>`).
