.. _dlb_contrib:

:mod:`dlb_contrib` -- Contributed tools and utilities
=====================================================

.. module:: dlb_contrib
   :synopsis: Contributed tools and utilities


dlb (the package) is completely tool agnostic.
Everything specific to a certain tool, language or file format is not part of dlb.

The package :mod:`dlb_contrib` contains such tools as well as utilities to generate input understood by the tools
and parsers for the output of the tools.

They are meant as starting points for your own tools and contributions which will
reside in your repositories.
The documentation is maintained only in the source files to make the modules self-contained.
Please see there for details.

.. dlbcontrib:module:: backslashescape
.. dlbcontrib:module:: zip
.. dlbcontrib:module:: make
.. dlbcontrib:module:: git
.. dlbcontrib:module:: clike
.. dlbcontrib:module:: gcc
.. dlbcontrib:module:: pkgconfig
.. dlbcontrib:module:: doxygen
.. dlbcontrib:module:: sh
.. dlbcontrib:module:: strace
.. dlbcontrib:module:: tex