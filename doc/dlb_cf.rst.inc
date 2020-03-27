:mod:`dlb.cf` --- Configuration parameters
==========================================

.. module:: dlb.cf
   :synopsis: Configuration parameters

To change the behaviour of dlb, change the values of the following variables.

.. data:: lastest_run_summary_max_count

   Number of dlb runs to summarize as an integer.

   When > 0, a summary of the latest *lastest_run_summary_max_count* dlb runs is output when a root context exits.

.. data:: max_dependency_age

   The maximum age of dependency information in the :term:`run-database` as a :class:`python:datatime.timedelta` object.

   Run and dependency information older than *max_dependency_age* is removed when a root context is entered.
   ``max_dependency_age > datetime.timedelta(0)`` must be ``True``.

.. module:: dlb.cf.level
   :synopsis: Categorical message levels

.. data:: RUN_PREPARATION
.. data:: RUN_PREPARATION
.. data:: RUN_SERIALIZATION
.. data:: REDO_NECESSITY_CHECK
.. data:: REDO_REASON
.. data:: REDO_SUSPICIOUS_REASON
.. data:: REDO_PREPARATION
.. data:: REDO_START
.. data:: REDO_AFTERMATH
.. data:: HELPER_EXECUTION
.. data:: RUN_SUMMARY

   Assign a message level (a positive integer like :data:`dlb.di.INFO`) to be used for all message of a given
   category.
