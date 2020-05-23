:mod:`dlb` --- Version
======================

.. module:: dlb
   :synopsis: Version

.. data:: __version__

   The version of dlb as a non-empty string.
   Example: ``'1.2.3'``.

   Conforms to :pep:`396`, :pep:`386` and :pep:`440`.

   Contains the string ``'.dev'`` if and only if this a development version.
   For a development version, *__version__* looks like this: ``'1.2.3.dev30+317f'``.

.. data:: version_info

   The version of dlb as a non-empty tuple of non-negative integers and strings ``'a'`` ... ``'z'``,
   similar to :data:`python:sys.version_info`.
   Example: ``(1, 2, 3)``.

   Contains at least 3 members, the first 3 of them integers.
   Contains more than 3 members if and only if this is an unreleased version.
   For an unreleased version, *version_info* looks like this: ``(1, 2, 3, 'c', 4)``.

   Use it like this to compare (released) versions::

      assert (1, 0, 3) <= dlb.version_info  < (2,)

   .. note::
      For a development version, *version_info* carries less information than *__version__*.
