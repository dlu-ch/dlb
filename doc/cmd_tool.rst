:mod:`dlb.cmd.tool` --- Dependency-Aware Command-Line Tools
===========================================================
.. module:: dlb.cmd
   :synopsis: Dependency-Aware Command-Line Tools

This module provides classes to represent tools to be executed during the build process.

*Tools* are the workhorses of every build tools.

In dlb, tools are classes derived from :class:`dlb.cmd.Tool`.
Tool instances are immutable and hashable;
tools are customized by inheritance and defining class attributes.


Tool Objects
------------

.. class:: Tool

   A tool declares its *dependency roles* (e.g. ``map_file_dependency``) and *execution parameters*
   (e.g. ``DO_INCLUDE_DEBUG_INFO``, ``PAPER_FORMAT``) as class attributes.

   Every tool instance assigns concrete objects for the tool's dependency roles
   (e.g. a filesystem path ``'./out/hello.map'`` for a dependency role ``map_file_dependency``),
   while the execution parameters are the same of all instances of the some tool.

   A new tool ``T`` can be defined by inheriting from one or more other tools.
