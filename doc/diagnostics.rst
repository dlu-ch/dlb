Diagnostics
===========

Informative messages
--------------------

Clang_ shows what precision and expressiveness in diagnostic messages mean.



Exceptions
----------

The exception messages of dlb are formed of one or multiple line, each representing a statement.

The first line is the summary.

Each following line represents a detail related to the first line and starts with ``'  | '``.


.. module:: dlb.ex.context

.. exception:: NotRunningError

   Raised, when an action requires a :term:`root context` while :term:`dlb was not running <run of dlb>`.

.. exception:: NoWorkingTreeError

   Raised, when the working directory of the calling process is not a :term:`working tree`'s root.

.. exception:: ManagementTreeError

   Raised, when an attempt to prepare or access the :term:`management tree` failed.

.. exception:: NestingError

   Raised, when some contexts were not properly nested.
   I.e. the calls of :meth:`__exit__` did not occur in the opposite order of the corresponding calls of
   :meth:`__enter__`.

.. _Clang: http://clang.llvm.org/diagnostics.html
