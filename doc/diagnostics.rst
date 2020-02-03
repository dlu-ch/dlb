Diagnostics
===========

Informative messages
--------------------

Clang_ shows what precision and expressiveness in diagnostic messages mean.


Exceptions
----------

.. module:: dlb.context

.. exception:: NoneActive

   There is no :term:`active context` (because :term:`dlb is not running <run of dlb>`).

.. exception:: NestingError

   Some parent context of the :term:`active context` changed inadmissibly.

.. _Clang: http://clang.llvm.org/diagnostics.html
