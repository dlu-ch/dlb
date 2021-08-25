Reference
*********

.. include:: terms.rst.inc
.. include:: worktreelayout.rst.inc
.. include:: toplevelspec.rst.inc
.. include:: dlbexe.rst.inc

.. include:: dlb.rst.inc
.. include:: dlb_fs.rst.inc
.. include:: dlb_di.rst.inc
.. include:: dlb_cf.rst.inc
.. include:: dlb_ex.rst.inc
.. include:: dlb_contrib.rst.inc


.. _POSIX:
.. _ISO 1003.1-2008: https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/contents.html
.. _hashable: https://docs.python.org/3/glossary.html#term-hashable


.. rubric:: Footnotes

.. [#machinereadable]
   Possible application: monitoring of the build progress on a build server.

.. [#mmap1]
   The update of :term:`mtime` for an ``mmap``'d file
   `conforming to ISO 1003.1-2008 <https://pubs.opengroup.org/onlinepubs/9699919799/functions/mmap.html>`_
   after a write to the mapped memory is only guaranteed via :c:func:`!msync()`.
   Therefore such a write operation is not considered complete before the next call of :c:func:`!msync()`
   (which may never happen).
   Actual behaviour of ``mmap`` on different operating systems (2018): https://apenwarr.ca/log/20181113.

.. [#touch1]
   Especially, :term:`mtime` is not manually set with :command:`touch -t` or any tool that uses a coarser time
   resolution than the :term:`effective mtime resolution`.
   See `touch <https://man7.org/linux/man-pages/man1/touch.1.html>`_  and
   `utimensat() <https://man7.org/linux/man-pages/man2/utimensat.2.html>`_.

.. [#linuxfstime1]
   Linux currently (2020) `uses <https://elixir.bootlin.com/linux/v5.5/source/fs/inode.c#L2220>`_
   `ktime_get_coarse_real_ts64() <https://www.kernel.org/doc/html/latest/core-api/timekeeping.html>`_ as time source
   for its (optional) :term:`mtime` updates, which
   `returns the system-wide realtime clock at the last tick <https://lwn.net/Articles/347811/>`_.

.. [#lazytime1]
   Some filesystems support mount options to sacrifice this guaranteed for performance.
   Example: Ext4 with mount option `lazytime <https://lwn.net/Articles/620086/>`_.

.. [#adjtime1]
   :c:func:`!adjtime()` is not covered by `ISO 1003.1-2008`_.
   It originated in 4.3BSD and System V.
   For many operating systems it states "the clock is always monotonically increasing"
   (`Linux <https://man7.org/linux/man-pages/man3/adjtime.3.html>`_,
   `OpenBSD <https://man.openbsd.org/adjtime>`_,
   `FreeBSD <https://www.freebsd.org/cgi/man.cgi?query=adjtime&sektion=2>`_).
