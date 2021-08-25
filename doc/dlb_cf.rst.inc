:mod:`dlb.cf` --- Configuration parameters
==========================================

.. module:: dlb.cf
   :synopsis: Configuration parameters

To change the behaviour of dlb, change the values of the following variables.

.. data:: latest_run_summary_max_count

   Number of dlb runs to summarize as an integer.

   When > 0, a :meth:`summary <dlb.ex.Context.summary_of_latest_runs()>` of the latest
   *latest_run_summary_max_count* dlb runs is output as a diagnostic message when a root context exits.

.. data:: max_dependency_age

   The maximum age of dependency information in the :term:`run-database` as a :class:`python:datetime.timedelta` object.

   Run and dependency information older than *max_dependency_age* is removed when a root context is entered.

   ``max_dependency_age > datetime.timedelta(0)`` must be ``True``.

.. data:: execute_helper_inherits_files_by_default

   Default value for output files of :meth:`dlb.ex.RedoContext.execute_helper()` etc..

   ``False`` means: Output is suppressed by default.
   ``True`` means: Output file is inherited from the Python process by default.

.. module:: dlb.cf.level
   :synopsis: Categorical message levels

.. data:: run_preparation
.. data:: run_serialization
.. data:: redo_necessity_check
.. data:: redo_reason
.. data:: redo_suspicious_reason
.. data:: redo_preparation
.. data:: redo_start
.. data:: redo_aftermath
.. data:: helper_execution
.. data:: output_filesystem_object_replacement
.. data:: run_summary

   :ref:`Message level <dlb-di-levels>` (a positive integer like :data:`dlb.di.INFO`) to be used for all diagnostic
   messages of the category named by the attribute's name.
