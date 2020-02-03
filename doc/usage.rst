Usage overview
==============

Recommendations
---------------

These recommendation describe the typical use case.
Use them as a starting point for most efficient and reliable operation. [#make1]_


Setup a working tree
^^^^^^^^^^^^^^^^^^^^

 - Place the entire :term:`working tree` on the same file system with a decently fine
   :term:`effective mtime resolution` (no courser than 100 ms). XFS or Ext4 are fine. Avoid FAT32. [#workingtreefs1]_

   Make sure the filesystem is mounted with "normal" (immediate) update of :term:`mtime`
   (e.g. without `lazytime` for Ext4). [#mountoption1]_

 - Place all inputs (that are only read by tool instances) in a filesystem tree in the :term:`working tree` that is not
   modified by tool instances.

   This is not required, but good practice.
   It also enables you to use operating system specific possibility to protect the build against accidental changes
   of input files.
   For example: Protect the inputs from change by a transparent read-only filesystem mounted on top of it during the
   build.


 - Do not use symbolic links in the managed tree to filesystem objects not in the same managed tree.


Run dlb
^^^^^^^

 - Do not modify the :term:`management tree` unless told so by dlb. [#managementtree1]_

 - Do not modify the :term:`mtime` of filesystem objects in the :term:`working tree` *manually* while
   :term:`dlb is running <run of dlb>`. [#touch1]_

 - Do not modify the content of filesystem objects in the :term:`managed tree` *on purpose* while
   :term:`dlb is running <run of dlb>`, if they are used as inputs or outputs of a tool instance.

   Yes, I know: it happens a lot by mistake when editing source files.

   dlb itself is designed to be relatively robust to such modifications.
   As long as the size of modified regular file changes or the :term:`working tree time` is monotonic, there is no
   :term:`redo miss` in the current or in any future :term:`run of dlb`. [#managedtree1]_ [#make3]_

   However, many external tools cannot guarantee proper behaviour if some of their input files are changed while they
   are being executed (e.g. a compiler working on multiple input files).

 - Avoid :command:`mv` to replace regular files; is does not update its target's :term:`mtime`.

   Use :command:`cp` instead.

 - Be careful when you modify inputs of a :term:`tool instance` via `mmap`. [#mmap1]_

 - Do not put the system time used as :term:`working tree's system time` back *on purpose* while
   :term:`dlb is running <run of dlb>` or while you are modifying the :term:`managed tree`. [#workingtreetime]_


Write scripts and tools
^^^^^^^^^^^^^^^^^^^^^^^

 - Do not modify the :term:`managed tree` in a :term:`script` inside a :term:`root context`, e.g. by calling
   :func:`shutil.rmtree()` directly. [#managedtree1]_

   Use :term:`tool instances <tool instance>` instead.

 - It is safe to modify the :term:`managed tree` immediately after a :term:`run of dlb` is completed (e.g. in the same
   :term:`script`, without risking a :term:`redo miss` [#make2]_

 - Do not use (explicit) multithreading. Use :py:mod:`asyncio` instead.

 - Do not use multiple hierarchical :term:`scripts <script>` (where one calls another).
   This would be error-prone an inefficient.
   Use scripts only on the top-level.

 - Split large :term:`scripts<script>` into small modules that are imported by the script.
   You can place these modules in the directory they control.

 - Use only *one* :term:`root context` and nest all other contexts inside
   (even in modules imported inside this context). [#rootcontext1]_

   Do::

       import dlb.ex
       ...
       with dlb.ex.Context():
           with dlb.ex.Context():
               ...
           with dlb.ex.Context():
               ...
           import build_subsystem_a  # contains 'with dlb.ex.Context(): ... '


   Don't::

       import dlb.ex
       ...

       with dlb.ex.Context():
          ...  # context manager exit is artificially delayed as necessary according to the
               # filesystem's effective mtime resolution

       with dlb.ex.Context():
          ...  # context manager exit is artificially delayed as necessary according to the
               # filesystem's effective mtime resolution (again)

 - Use context to serialize groups of running tool instances, even when running in parallel [#serialize1]_::

       with dlb.ex.Context(max_tool_processes=4):
           ...

       ...  #  all running tool instances are completed here

       with dlb.ex.Context():
           ...


Layout of working tree
----------------------

The directory :file:`.dlbroot/` is mandatory (it marks its parent directory the root of a dlb working tree).
Everything else

It can by useful to include dlb as :file:`dlb.zip` in the working tree (under version control). This makes the
working tree almost self-contained (an external Python interpreter is needed).

If you use Git for version control which does not support empty directories, add an empty regular file
:file:`.dlbroot/o`.

The lines marked with * show filesystem object only given as an example.

**Before** first run of a dlb script:

::

   .dlbroot/
   src/                    *
      a.c                  *
      a.h                  *
      b.c                  *
   test/                   *
   ...

**During** a run of a dlb script (:file:`.dlbroot/t/a.o` and :file:`test/` and their content are only given as an
example):

::

   .dlbroot/
       o                   empty regular file, used to probe the "current" mtime
       runs.sqlite
       t/                  temporary files
           a.o             *
           b.o             *
    src/                   *
      a.c                  *
      a.h                  *
      b.c                  *
    test/                  *
    out/                   *
      p                    *
    dist/                  *
    ...


**After** a successful run of a dlb script:

::

   .dlbroot/
       o                   empty regular file
       runs.sqlite         state of the past running tool instances
    src/                   *
      a.c                  *
      a.h                  *
      b.c                  *
    test/                  *
    out/                   *
      a.o                  *
      b.o                  *
    dist/                  *
      p                    *
    ...

.. _Make: https://en.wikipedia.org/wiki/Make_%28software%29

.. [#make1]
   Although they are not formally specified, Make_ has by design much stricter requirements and much looser guarantees.
.. [#workingtreefs1] |assumption-f1|, |assumption-t3|
.. [#mountoption1] |assumption-f2|, |assumption-f3|, |assumption-f4|
.. [#managementtree1] |assumption-a1|
.. [#managedtree1]
   |assumption-a2|, |guarantee-d1|, |guarantee-d2|, |guarantee-d3|
.. [#make3]
   Make_ is very vulnerable to this.
   Even with a monotonically increasing :term:`working tree time`, the inputs (sources of a rule) must not be changed
   from the moment its recipe's execution is started until the next increase of the :term:`working tree time` after
   the recipe's execution is completed.
   Otherwise, there is a :term:`redo miss` in every future run - until the :term:`working tree time` a an input is
   changed again in a way that does not cause a redo miss.
.. [#make2] This is not the case with Make_.
.. [#rootcontext1] |guarantee-t2|
.. [#workingtreetime] |assumption-t2| |guarantee-d1|, |guarantee-d3|
.. [#serialize1] |guarantee-t1|
.. [#touch1] |assumption-a3|
.. [#mmap1] |assumption-f3|

.. |assumption-a1| replace:: :ref:`A-A1 <assumption-a1>`
.. |assumption-a2| replace:: :ref:`A-A2 <assumption-a2>`
.. |assumption-a3| replace:: :ref:`A-A3 <assumption-a3>`
.. |assumption-f1| replace:: :ref:`A-F1 <assumption-f1>`
.. |assumption-f2| replace:: :ref:`A-F2 <assumption-f2>`
.. |assumption-f3| replace:: :ref:`A-F3 <assumption-f3>`
.. |assumption-f4| replace:: :ref:`A-F4 <assumption-f4>`
.. |assumption-t1| replace:: :ref:`A-T1 <assumption-t1>`
.. |assumption-t2| replace:: :ref:`A-T2 <assumption-t2>`
.. |assumption-t3| replace:: :ref:`A-T3 <assumption-t3>`
.. |assumption-t4| replace:: :ref:`A-T4 <assumption-t4>`
.. |assumption-d2| replace:: :ref:`A-D2 <assumption-d2>`
.. |guarantee-t1| replace:: :ref:`G-T1 <guarantee-t1>`
.. |guarantee-t2| replace:: :ref:`G-T2 <guarantee-t2>`
.. |guarantee-d1| replace:: :ref:`G-D1 <guarantee-d1>`
.. |guarantee-d2| replace:: :ref:`G-D2 <guarantee-d2>`
.. |guarantee-d3| replace:: :ref:`G-D3 <guarantee-d3>`
