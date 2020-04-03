Usage
=====

Installation
------------

dlb is written in `Python`_ and requires at least Python 3.7.

The canonical way to install dlb is from the Python Package Index (`PyPI`_)::

   $ python3 -m pip install dlb

If you prefer not to install to the Python system location, or do not have privileges to do so, you can add a flag to
install to a location specific to your own account::

   $ python3 -m pip install --user dlb

After the successful installation, the dlb modules are ready for import by a Python 3 interpreter::

   >>> import dlb
   >>> dlb.__version__
   '1.2.3'

Check also the installed command-line utility [#installationlocation1]_::

   $ dlb --help

This shows you the location of all installed files::

   $ python3 -m pip show -f dlb

It is also possible to "install" dlb into a project as a ZIP archive.
See :ref:`here <manual-self-contained-project>` for details.


Update and uninstall
--------------------

Update an dlb installation with::

   $ python3 -m pip install --upgrade [ --user ] dlb

Uninstall it with::

   $ python3 -m pip uninstall [ --user ] dlb


A simple project
----------------

We assume that you want to build some software from a `Git`_ repository with dlb on a GNU/Linux system with a
`POSIX`_ compliant shell.
Let's call the project `hello`.

Create the Git working directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

First, create the repository::

   $ mkdir hello
   $ cd hello
   $ git init

dlb requires a :file:`.dlbroot` directory as a marker for the root of its :term:`working tree`, similar to :file:`.git`
of Git::

   $ mkdir .dlbroot

Now, the directory is ready for use by dlb as a working tree. dlb does not require or assume anything about existing
file or directories outside :file:`.dlbroot` (see :ref:`here <ref-workingtree-layout>` for details on the
directory layout).
We will use a :term:`dlb script <script>` called :file:`build.py` to build our project, so let's start with an
polite one::

   $ echo 'print("hello there!")' > build.py

Now, we can use :file:`dlb` to run :file:`build.py`::

   $ dlb build
   hello there!

Instead of ``dlb build`` we could also have used ``python3 "${PWD}"/build.py``. ``dlb`` comes in handy when you are
working in a subdirectory of the :term:`working tree` or when you need modules from ZIP archives
(e.g. :ref:`dlb itself <manual-self-contained-project>`)::

   $ mkdir src
   $ cd src
   $ dlb
   using arguments of last successful run: 'build.py'
   hello there!
   $ cd ..

See ``dlb --help`` for a detailed description.


Run a custom tool in an execution context
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Replace the content of :file:`build.py` by this::

   import dlb.ex

   class Replacer(dlb.ex.Tool):
       PATTERN = 'xxx'
       REPLACEMENT = 'hello'

       template = dlb.ex.Tool.Input.RegularFile()
       output = dlb.ex.Tool.Output.RegularFile()

       async def redo(self, result, context):
           with open(self.template.native, 'r') as i:
               c = i.read()  # read input
           with context.temporary() as t:
               with open(t.native, 'w') as o:
                   o.write(c.replace(self.PATTERN, self.REPLACEMENT))  # write transformed 'c' to temporary
               context.replace_output(result.output, t)  # atomically replace output by temporary

   with dlb.ex.Context():  # an execution context
       Replacer(template='src/main.c.tmpl', output='build/out/main.c').run()  # create a tool instance and run it


This defines a :term:`tool` called ``Replacer`` with an *input dependency* ``template`` and an *output
dependency* ``output``. The class attributes ``PATTERN`` and ``REPLACEMENT`` are *execution parameters* of the tool.
The method ``redo()`` is called by ``Replacer(...).run()`` if a :term:`redo` is necessary.

Create a file :file:`src/main.c.tmpl` with this content::

   // xxx
   #include <stdio.h>

   int main() {
       printf("xxx\n");
       return 0;
   }

When you run ``dlb`` now, you get something like::

   $ dlb build
   D check redo necessity for tool instance 1... [+0.000000s]
     D explicit output dependencies... [+0.000161s]
       I redo necessary because of filesystem object that is an output dependency: 'build/out/main.c'
         | reason: [Errno 2] No such file or directory: '/.../hello/build/out/main.c'
       D done. [+0.000264s]
     D done. [+0.000331s]
   I start redo for tool instance 1 [+0.014796s]

It informs you that a :term:`redo` was necessary for the :term:`tool instance` because the output dependency
:file:`build/out/main.c` did not exist.
It was created by the redo and now contains::

   // hello

   #include <stdio.h>

   int main() {
       printf("hello\n");
       return 0;
   }

Now run dlb again::

   $ dlb build

Nothing happens because the output existed and the input (including the tool definition in :file:`build.py`)
did not change. After a modification of the input dependency, dlb again causes a redo::

   $ touch src/src/main.c.tmpl
   $ dlb build
   D check redo necessity for tool instance 1... [+0.000000s]
     D compare input dependencies with state before last successful redo... [+0.000287s]
       I redo necessary because of filesystem object: 'src/main.c.tmpl'
         | reason: mtime has changed
       D done. [+0.000375s]
     D done. [+0.000385s]
   I start redo for tool instance 1 [+0.014572s]


Real stuff
^^^^^^^^^^

There are more meaningful tasks than replacing text in text file.

For example, building a C program with GCC looks like
`this <https://github.com/dlu-ch/dlb/blob/master/example/c-minimal/build-all.py>`_.

The package :mod:`dlb_contrib` provides tools and utilities to build upon.


Commit the changes
^^^^^^^^^^^^^^^^^^

Git does not track empty directories. If we want Git to create :file:`.dlbroot` as part of the repository, a file
must be added. We can use the file :file:`.dlbroot/o` created by the :term:`root context` of a previous
:term:`run of dlb` to that end::

   $ git add .dlbroot/o
   $ git commit


.. _manual-self-contained-project:

Self-contained project: add dlb to the repository
-------------------------------------------------

ZIP archives in :file:`.dlbroot/u/` are automatically added to the module search path of the Python interpreter
by :ref:`dlb <dlbexe>`. Placing the :mod:`dlb` package as a version controlled ZIP archive there
--- say, :file:`.dlbroot/u/dlb-1.2.3.zip` --- allows you to keep a certain version of dlb independent of a system-wide
installed version.


Recommendations for efficiency and reliability
----------------------------------------------

These recommendation describe the typical use case.
Use them as a starting point for most efficient and reliable operation. [#make1]_


Setup a working tree
^^^^^^^^^^^^^^^^^^^^

- Place the entire :term:`working tree` on the same file system with a decently fine
  :term:`effective mtime resolution` (no courser than 100 ms). XFS or Ext4 are fine. Avoid FAT32. [#workingtreefs1]_

  Make sure the filesystem is mounted with "normal" (immediate) update of :term:`mtime`
  (e.g. without ``lazytime`` for Ext4). [#mountoption1]_

- Place all input files (that are only read by tool instances) in a filesystem tree in the :term:`working tree`
  that is not modified by tool instances.

  This is not required but good practice.
  It also enables you to use operating system specific features to protect the build against accidental changes
  of input files.
  For example: Protect the input files from change by a transparent read-only filesystem mounted on top of it during
  the build.

- Do not use symbolic links in the managed tree to filesystem objects not in the same managed tree.


Run dlb
^^^^^^^

- Do not modify the :term:`management tree` unless told so by dlb. [#managementtree1]_

- Do not modify the :term:`mtime` of filesystem objects in the :term:`working tree` *manually* while
  :term:`dlb is running <run of dlb>`. [#touch1]_

- Do not modify the content of filesystem objects in the :term:`managed tree` *on purpose* while
  :term:`dlb is running <run of dlb>`, if they are used as input dependencies or output dependencies of a
  tool instance.

  Yes, I know: it happens a lot by mistake when editing source files.

  dlb itself is designed to be relatively robust to such modifications.
  As long as the size of modified regular file changes or the :term:`working tree time` is monotonic, there is no
  :term:`redo miss` in the current or in any future :term:`run of dlb`. [#managedtree1]_ [#make3]_

  However, many external tools cannot guarantee proper behaviour if some of their input files are changed while they
  are being executed (e.g. a compiler working on multiple input files).

- Avoid :command:`mv` to replace regular files; is does not update its target's :term:`mtime`.

  Use :command:`cp` instead.

- Be careful when you modify a file via ``mmap`` that is an input dependency of a :term:`tool instance`. [#mmap1]_

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

      with dlb.ex.Context(max_parallel_redo_count=4):
          ...

      ...  #  all running tool instances are completed here

      with dlb.ex.Context():
          ...


.. _POSIX:
.. _ISO 1003.1-2008: https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/contents.html
.. _Python: https://www.python.org/downloads/
.. _PyPI: https://pypi.org/project/dlb/
.. _Git: https://git-scm.com/
.. _Make: https://en.wikipedia.org/wiki/Make_%28software%29

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


.. rubric:: Footnotes

.. [#installationlocation1]
   When installed with ``python3 -m pip install --user dlb``, the command-line utility is created below
   ``python3 -m site --user-base`` according to :pep:`370`.
   Make sure this directory is part of the search paths for executables.

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
   Otherwise, there is a :term:`redo miss` in every future run --- until the :term:`working tree time` a an input is
   changed again in a way that does not cause a redo miss.

.. [#make2] This is not the case with Make_.

.. [#rootcontext1] |guarantee-t2|

.. [#workingtreetime] |assumption-t2| |guarantee-d1|, |guarantee-d3|

.. [#serialize1] |guarantee-t1|

.. [#touch1] |assumption-a3|

.. [#mmap1] |assumption-f3|
