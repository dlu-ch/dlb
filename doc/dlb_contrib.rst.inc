.. _dlb_contrib:

:mod:`dlb_contrib` -- Contributed tools and utilities
=====================================================

.. module:: dlb_contrib
   :synopsis: Contributed tools and utilities


dlb (the package) is completely tool agnostic.
Everything specific to a certain tool, language or file format is not part of dlb.

The package :mod:`dlb_contrib` contains such tools as well as utilities to generate input understood by the tools
and parsers for the output of the tools.


Overview
--------

.. dlbcontrib:moduleindex::


Details
-------

The modules in :mod:`dlb_contrib` are meant as starting points for your own tools and extensions which will
reside in your repositories.
Therefore, their documentation is maintained only in the source files to make them self-contained.
Please see there for details.

.. Order of the modules
   - module without tool classes before module with tool classes
   - a before b if b imports a
   - simple modules before complicated modules

.. dlbcontrib:module:: backslashescape
.. dlbcontrib:module:: iso6429
.. dlbcontrib:module:: exctrace
.. dlbcontrib:module:: partition
.. dlbcontrib:module:: exportenv
.. dlbcontrib:module:: generic
.. dlbcontrib:module:: zip
.. dlbcontrib:module:: versioned_interface
.. dlbcontrib:module:: linux
.. dlbcontrib:module:: git
.. dlbcontrib:module:: gnumake
.. dlbcontrib:module:: gnubinutils
.. dlbcontrib:module:: clike
.. dlbcontrib:module:: gcc
.. dlbcontrib:module:: msbatch
.. dlbcontrib:module:: msvc
.. dlbcontrib:module:: pkgconfig
.. dlbcontrib:module:: doxygen
.. dlbcontrib:module:: sh
.. dlbcontrib:module:: strace
.. dlbcontrib:module:: tex
