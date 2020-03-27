.. _dlbexe:

:command:`dlb` --- Command-line utility for convenience
=======================================================

The command-line utility :command:`dlb` calls a :term:`dlb script <script>`;
the real work is done entirely by the dlb script with the help of the package :mod:`dlb`.

:command:`dlb` can save you some typing, however, with the following features:

- Changes the current working directory to the working tree's root from anywhere in the :term:`working tree`.
- Remembers command-line arguments of the last successful call.
- Adds ZIP archives to the module search path.

See ``dlb --help`` for details.
