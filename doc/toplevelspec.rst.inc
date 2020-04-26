Top-level specification
=======================

Assumptions
-----------

An assumption (**A-**...) is a requirement for the intended behaviour of dlb that cannot be checked at runtime in a
reliable and efficient way.

For every assumption at set of acceptable effects of its violation is given:

   .. _assumptionviolationeffect-repair:
   .. |assumptionviolationeffect-repair| replace:: :ref:`repair <assumptionviolationeffect-repair>`

   repair
      The working tree needs manual repair.

   .. _assumptionviolationeffect-obscure-fail:
   .. |assumptionviolationeffect-obscure-fail| replace:: :ref:`obscure-fail <assumptionviolationeffect-obscure-fail>`

   obscure-fail
      A build may fail in an obscure way. The diagnostic messages do neither clearly indicate the problem nor
      a way to fix it.

   .. _assumptionviolationeffect-vulnerable:
   .. |assumptionviolationeffect-vulnerable| replace:: :ref:`vulnerable <assumptionviolationeffect-vulnerable>`

   vulnerable
      The build becomes vulnerable to attacks.
      Running :term:`tool instances <tool instance>` might overwrite any filesystem object the process has permission
      to, potentially with information generated during the build or stored in the working tree.

   redo-miss
      A :term:`redo miss` in the current or a future :term:`run of dlb` can occur.

   .. _assumptionviolationeffect-graceful-fail:
   .. |assumptionviolationeffect-graceful-fail| replace:: :ref:`graceful-fail <assumptionviolationeffect-graceful-fail>`

   graceful-fail
      A build may fail in a meaningful way. The diagnostic messages clearly indicate the problem or a way to fix it.

   .. _assumptionviolationeffect-redo-miss:
   .. |assumptionviolationeffect-redo-miss| replace:: :ref:`redo-miss <assumptionviolationeffect-redo-miss>`


Modification of the working tree
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _assumption-a1:
.. |assumption-a1| replace:: :ref:`A-A1 <assumption-a1>`

**A-A1** (access to management tree)
   Except for modifications by dlb internals, the :term:`management tree` is not modified while
   :term:`dlb is running <run of dlb>` and only as suggested by diagnostic messages of dlb.

   Changing the absolute path of the :term:`working tree`'s root is considered a modification.

   Acceptable when violated:

   - |assumptionviolationeffect-repair|
     (e.g. after the :term:`run-database` has become corrupted)
   - |assumptionviolationeffect-obscure-fail|
     (e.g. after intermediate files have been modified)
   - |assumptionviolationeffect-vulnerable|
     (e.g. by a symlink attack)
   - |assumptionviolationeffect-redo-miss|
     (e.g. after the :term:`run-database` has been is tampered with)
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-a2:
.. |assumption-a2| replace:: :ref:`A-A2 <assumption-a2>`

**A-A2** (access to managed tree)
   While a :term:`tool instance` in running, the :term:`managed tree` is modified only by running tool instances.

   Changing the absolute path of the working tree's root is considered a modification.

   Acceptable when violated:

   - |assumptionviolationeffect-obscure-fail|
     (e.g. when a running tool instance "sees" an intermediate state of files that are input dependencies)
   - |assumptionviolationeffect-vulnerable|
     (e.g. by a symlink attack)
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-a3:
.. |assumption-a3| replace:: :ref:`A-A3 <assumption-a3>`

**A-A3** (manual modification of mtime)
   Except from modifications requested by a running :term:`tool instance`, every modification of the :term:`mtime` of a
   filesystem object in the working tree is a :term:`mtime update`. [#touch1]_

   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-a4:
.. |assumption-a4| replace:: :ref:`A-A4 <assumption-a4>`

**A-A4**
   No part of the filesystem outside of the :term:`working tree` is modified while a :term:`tool instance` *t* is
   running, unless it cannot affect the behaviour of *t*.

   Acceptable when violated:

   - |assumptionviolationeffect-obscure-fail|
   - |assumptionviolationeffect-vulnerable|
   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|


Filesystems behaviour of working tree
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. _assumption-f1:
.. |assumption-f1| replace:: :ref:`A-F1 <assumption-f1>`

**A-F1** (one filesystem)
   Every filesystem object :file:`{w}/{p}`, where :file:`{w}` is the path of the :term:`working tree`'s root and
   :file:`{p}` is a relative path without :file:`..` components, resides on the same (local or remote) file system.

   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-f2:
.. |assumption-f2| replace:: :ref:`A-F2 <assumption-f2>`

**A-F2** (mtime update at creation)
   Every creation of a filesystem object in the :term:`working tree` :term:`updates its mtime <mtime update>`.
   [#lazytime1]_

   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-f3:
.. |assumption-f3| replace:: :ref:`A-F3 <assumption-f3>`

**A-F3** (mtime update at write to regular file)
   Every write to regular file in the :term:`working tree` :term:`updates its mtime <mtime update>` as soon as it is
   completed. [#lazytime1]_ [#mmap1]_

   Between start and completion of a write, a reader of the file may observe an intermediate state of the
   file's content.

   ::

      [--------------] content change

      ^              ^
      start          mtime update (write complete)

      -------------------> ideal time


   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-f4:
.. |assumption-f4| replace:: :ref:`A-F4 <assumption-f4>`

**A-F4** (mtime update for directory)
   Every creation, removal, renaming and attribute change of a filesystem object in the
   :term:`working tree` :term:`updates the mtime <mtime update>` of the (directly) containing directory.
   [#lazytime1]_

   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-f5:
.. |assumption-f5| replace:: :ref:`A-F5 <assumption-f5>`

**A-F5** (moving is atomic)
   Moving a regular file, a directory or a symbolic link in the :term:`working tree` to a different directory in
   the working tree is possible in an reasonably secure, efficient and atomic operation that does not affect the moved
   object's filesystem attributes (including :term:`mtime` in full resolution).

   Acceptable when violated:

   - |assumptionviolationeffect-graceful-fail|

.. _assumption-f6:
.. |assumption-f6| replace:: :ref:`A-F6 <assumption-f6>`

**A-F6** (moving makes invisible)
   Immediately after a regular file, a directory or a symbolic link in the :term:`working tree` has been
   successfully moved to a different directory within the same working tree, no other process "sees" it in
   the original directory.

   Acceptable when violated:

   - |assumptionviolationeffect-obscure-fail|
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-f7:
.. |assumption-f7| replace:: :ref:`A-F7 <assumption-f7>`

**A-F7** (no corruption)
   A filesystem object in :term:`working tree` is never corrupted (e.g. by failure of software, memory or power).

   Acceptable when violated:

   - |assumptionviolationeffect-repair|
   - |assumptionviolationeffect-obscure-fail|
   - |assumptionviolationeffect-vulnerable|
   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|


Timing and concurrency
^^^^^^^^^^^^^^^^^^^^^^

.. _assumption-t1:
.. |assumption-t1| replace:: :ref:`A-T1 <assumption-t1>`

**A-T1** (working tree time exists)
   The :term:`mtime` of every filesystem object in the working tree is updated from the same system time
   (local or remote), the working tree's system time.
   Whenever a :term:`mtime update` occurs for a filesystem object *p* after one occurs for
   filesystem object *q*, where *p* and *q* are in the working tree, the :term:`mtime`
   of *p* is not later than the :term:`mtime` of *q*. [#linuxfstime1]_

   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-t2:
.. |assumption-t2| replace:: :ref:`A-T2 <assumption-t2>`

**A-T2** (working tree time mostly monotonically increasing)
   With the exception of rare backward jumps, the :term:`working tree time` is monotonically increasing.

   The time between consecutive backward jumps is longer than the duration of a :term:`run of dlb`.

   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
     (the finer the :term:`effective mtime resolution` and the less frequent modification of inputs files are,
     the less likely is a :term:`redo miss` due to this violation)
   - |assumptionviolationeffect-graceful-fail|
     (this is desirable since it forces correction before it can cause redo misses in the future)

.. _assumption-t3:
.. |assumption-t3| replace:: :ref:`A-T3 <assumption-t3>`

**A-T3** (effective mtime resolution)
   The regular file :file:`o` in the :term:`management tree` has an :term:`effective mtime resolution` no coarser
   than 100 ms.

   Acceptable when violated:

   - |assumptionviolationeffect-graceful-fail|

.. _assumption-t4:
.. |assumption-t4| replace:: :ref:`A-T4 <assumption-t4>`

**A-T4** (working tree time of true input dependencies in the past)
   The :term:`mtime` of every filesystem object in the managed tree that is an :term:`true input dependency` of a
   :term:`tool instance` *t* is earlier than the time *t* starts running.

   Acceptable when violated:

   - |assumptionviolationeffect-graceful-fail|


Dependencies
^^^^^^^^^^^^

.. _assumption-d1:
.. |assumption-d1| replace:: :ref:`A-D1 <assumption-d1>`

**A-D1** (regular files)
   Most of the filesystem objects in the managed tree that serve as input dependency of
   :term:`tool instances <tool instance>` are regular files.

.. _assumption-d2:
.. |assumption-d2| replace:: :ref:`A-D2 <assumption-d2>`

**A-D2** (no links to input dependencies)
   A filesystem object in the :term:`managed tree` that serves as an input dependency of a :term:`tool instance`
   has no hard link or symbolic link pointing to it in the :term:`managed tree`.

   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|

.. _assumption-d3:
.. |assumption-d3| replace:: :ref:`A-D3 <assumption-d3>`

**A-D3** (no implicit symbolic links in paths)
   A filesystem object in the :term:`managed tree` that serves as a dependency of a :term:`tool instance` *t* does not
   have a parent directory :file:`{p}` in its path that is a symbolic link, unless :file:`{p}` is an input dependency
   of *t* and in the working tree.

   Acceptable when violated:

   - |assumptionviolationeffect-redo-miss|
   - |assumptionviolationeffect-graceful-fail|


Guarantees
----------

A guarantee (**G-**...) is a specification of behaviour observable by the user.


Dependencies
^^^^^^^^^^^^

.. _guarantee-d1:
.. |guarantee-d1| replace:: :ref:`G-D1 <guarantee-d1>`

**G-D1** (no redo miss when working tree time monotonic)
   A :term:`benign managed tree modification` is :term:`redo-safe`,
   provided the assumptions |assumption-f1|, |assumption-f2|, |assumption-f3|, |assumption-f4| hold and the
   :term:`working tree time` is monotonically increasing (at least since the oldest :term:`mtime` of all
   filesystem objects that are :term:`true input dependencies <true input dependency>` of a :term:`tool instance`).

   This is true even when assumption |assumption-a2| is violated.

.. _guarantee-d2:
.. |guarantee-d2| replace:: :ref:`G-D2 <guarantee-d2>`

**G-D2** (no redo miss when file size changes)
   Modifying the content of a regular file in the managed tree while a :term:`tool instance` is running (in violation of
   |assumption-a2|) is :term:`redo-safe` if it also changes the size of the regular file.

.. _guarantee-d3:
.. |guarantee-d3| replace:: :ref:`G-D3 <guarantee-d3>`

**G-D3** (redo miss unlikely when modification intervals relatively long)
   A :term:`benign managed tree modification` is likely to be :term:`redo-safe`,
   provided the assumptions |assumption-f1|, |assumption-f2|, |assumption-f3|, |assumption-f4| hold and
   the "modification intervals are relatively long" for every filesystem object that is a :term:`true input dependency`
   of a :term:`tool instance`.

   Here a modification interval of a filesystem object *p* is considered to be relatively long if
   it is unlikely that the :term:`working tree time` at the :term:`ideal time` *t* is the same as at *t* + *T*,
   where *T* is the :term:`ideal time` between two consecutive :term:`mtime updates <mtime update>` of *p*.

   This is true even when assumption |assumption-a2| is violated.

.. _guarantee-d4:
.. |guarantee-d4| replace:: :ref:`G-D4 <guarantee-d4>`

**G-D4**
   When assumption |assumption-t2| is violated at a certain time at the start of the "redo check" phase of a running
   :term:`tool instance`, the build is aborted with a meaningful diagnostic message. [#resolution1]_


Timing and concurrency
^^^^^^^^^^^^^^^^^^^^^^

.. _guarantee-t1:
.. |guarantee-t1| replace:: :ref:`G-T1 <guarantee-t1>`

**G-T1** (active context exit)
   An :term:`active context` is not left as long as a :term:`tool instance` is running in it.

.. _guarantee-t2:
.. |guarantee-t2| replace:: :ref:`G-T2 <guarantee-t2>`

**G-T2** (root context exit)
   A :term:`root context` is not left other than by a raised exception before there has been a time window with the
   following property:
   The :term:`mtime` of a regular file o in the :term:`management tree` would have been different from the
   :term:`mtime` of the last filesystem object modified by a running :term:`tool instance`.

.. _guarantee-t3:
.. |guarantee-t3| replace:: :ref:`G-T3 <guarantee-t3>`

**G-T3** (multiple dlb processes)
   When multiple scripts are run by different processes on the same :term:`working tree`, at most one of them is in
   an :term:`active context` at the same time.

.. _guarantee-t4:
.. |guarantee-t4| replace:: :ref:`G-T4 <guarantee-t4>`

**G-T4** (threads)
   dlb does not create threads.

