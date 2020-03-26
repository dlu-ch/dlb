:mod:`dlb` --- Version
======================

.. module:: dlb
   :synopsis: Version

.. data:: __version__

   The version of dlb as a non-empty string.
   Example: ``'1.2.3``.

   Conforms to :pep:`396`, :pep:`386` and :pep:`440`.

   Contains the string ``'.dev'`` if and only if this a development version.
   For a development version, *__version__* looks like this: ``'1.2.3.dev30+317f'``.

.. data:: version_info

   The version of dlb as a tuple of at least three members, similar to :data:`python:sys.version_info`.
   Each member is a non-negative integer or a string ``'a'`` ... ``'z'``.
   The first tree members are integers.
   Example: ``(1, 2, 3, 'c', 4)``.

   Use it like this to compare versions::

      assert (1, 0) <= dlb.version_info  < (2,)

   Note: For a development version, *version_info* carries less information than *__version__*.
