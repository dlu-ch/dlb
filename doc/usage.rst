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

       template_file = dlb.ex.input.RegularFile()
       output_file = dlb.ex.output.RegularFile()

       async def redo(self, result, context):
           with open(self.template_file.native, 'r') as i:
               c = i.read()  # read input
           with context.temporary() as t:
               with open(t.native, 'w') as o:
                   o.write(c.replace(self.PATTERN, self.REPLACEMENT))  # write transformed 'c' to temporary
               context.replace_output(result.output_file, t)  # atomically replace output_file by temporary

   t = Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c')  # create a tool instance
   with dlb.ex.Context():  # an execution context
       t.run()  # run the tool instance in the active execution context


This defines a :term:`tool` called ``Replacer`` with an *input dependency role* ``template_file`` and an *output
dependency role* ``output_file``. The class attributes ``PATTERN`` and ``REPLACEMENT`` are *execution parameters* of the
tool. The method ``redo()`` is called by ``t.run()`` if a :term:`redo` is necessary.

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


Understand redo necessity
^^^^^^^^^^^^^^^^^^^^^^^^^

Everything related to dependency checking and :term:`redos <redo>` is centered around
:term:`tool instances <tool instance>`; only tool instances can have dependencies.

This line creates a tool instance *t* that assigns the concrete input dependency ``dlb.fs.Path('src/main.c.tmpl')`` to
the input dependency role ``template_file`` and the concrete output dependency ``dlb.fs.Path('build/out/main.c')`` to
the output dependency role ``output_file``::

   t = Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c')

``t.run()`` performs a redo when

a. one it explicitly requested by ``t.run(force_redo=True)`` or
b. a redo is considered necessary (see :term:`here <redo necessity>` for general conditions and the documentation of
   the dependency classes for the specific ones).

After the successful completion of a redo of a tool instance *t* the :term:`run-database` contains the depended-upon
state of its (explicit and non-explicit) input dependencies before the start of the redo and its non-explicit
input dependencies.

A redo of *t* from above is considered necessary if at least one of the following conditions is true:

- A redo was never performed successfully before for *t* (same class and fingerprint) according to the
  :term:`run-database`.
- :file:`build/out/main.c` does not exist as a regular file.
- The :term:`mtime`, size, UID, GID, or set of access permissions of :file:`src/main.c.tmpl` has changed since the
  start of the last known successful redo for *t* (because it is an output dependency of *t*)
- The value of ``PATTERN`` or ``REPLACEMENT`` has changed since the the last known successful redo for *t*.
- The :term:`mtime`, size, UID, GID, or set of access permissions of :file:`build.py` has changed since the last known
  successful redo of *t* (because :file:`build.py` is a definition file for *t* in the :term:`managed tree`).

Tool instances are identified by their class (file path and line number of definition) and their fingerprint.
The fingerprint includes the concrete dependencies of the tool instance which are defined by arguments of the
constructor matching class attributes.
Consider the following tool instances::

    t2 = Replacer(template_file=dlb.fs.Path('src/main.c.tmpl'), output_file='build/out/main.c')
    t3 = Replacer(template_file='src/MAIN.C.TMPL', output_file='build/out/main.c')

*t2* and *t* have the same same class and fingerprint and are therefore indistinguishable with respect to dependencies;
the statements ``t.run()`` and ``t2.run()`` have the same effect under all circumstances.
*t3* on the other hand has a different fingerprint; ``t3.run()`` does not affect the last known successful redo for *t*.

.. note::
   dlb never stores the state of filesystem objects outside the :term:`working tree` in its :term:`run-database`.
   The modification of such a filesystem object does *not* lead to a redo.
   [#dependenciesoutsideworkingtree1]_


Understand redo concurrency
^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``t.run()`` "performs a redo" it schedules the eventual (asynchronous) execution of
:meth:`redo() <dlb.ex.Tool.redo>` and then returns immediately. The completion of the pending redo is left to
:mod:`asyncio`.

So, redos are parallel by default. The maximum number of pending redos at a time is given by
:attr:`max_parallel_redo_count <dlb.ex.Context.max_parallel_redo_count>` of the :term:`active context`.

In contrast to GNU Make or Ninja, for example, filesystem paths used in multiple tool instances do *not* form an
implicit mutual exclusion mechanism. Synchronization and ordering of events is explicit in dlb.
Redos can be synchronized

a) globally for all pending redos by the means of :term:`(execution) contexts <context>` or
b) selectively for a specific redo by accessing the result (proxy) object return by :meth:`dlb.ex.Tool.run()`.

See :meth:`dlb.ex.Tool.run()` for details.

As a rule, paths `should not be repeated <https://en.wikipedia.org/wiki/Don%27t_repeat_yourself>`_ like
:file:`build/out/main.c` in this snippet (which may execute the redos of ``Replacer(...)`` and ``CCompiler(...)``
in parallel)::

  Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c').run()
  CCompiler(source_files=['build/out/main.c'], object_files=['build/out/main.c.o']).run()

Better use a variable whose name expresses the meaning of the filesystem object or cascade tool instances with their
result objects. Write this, for example, if you want to express that one tool instance depends on the result of
another one::

  r = Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c').run()
  CCompiler(source_files=[r.output_file], object_files=['build/out/main.c.o']).run()
  # waits for pending redo with result r to complete before CCompiler(...).run()

This mechanism is used in `example/c-minimal/`_.

Alternatively, you could wait for *all* pending redos to complete before ``Compiler(...).run()`` if you prefer
to split the build into sequential phases like this::

  # code generation phase
  Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c').run()

  # compilation phase
  with dlb.ex.Context():  # waits for all pending redos to complete
      CCompiler(source_files=['build/out/main.c'], object_files=['build/out/main.c.o']).run()

This mechanism is used in `example/c-gtk/`_.


Control the output verbosity
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

dlb is configured by *configuration parameters* in :mod:`dlb.cf`.

You want to know how exactly dlb calls the external tools and like some output after *each* run?
Add the following lines to :file:`build.py` (before the line ``with dlb.ex.Context():``)::

  import dlb.di
  import dlb.cf

  dlb.cf.level.helper_execution = dlb.di.INFO
  dlb.cf.latest_run_summary_max_count = 5

This instructs dlb to use the log level :data:`dlb.di.INFO` for all future diagnostic messages of the category
:data:`dlb.cf.level.helper_execution` and to output a summary after each run that compares the run with the
previous ones.


Real stuff
^^^^^^^^^^

There are more meaningful tasks than replacing text in a text file.

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
--- say, :file:`.dlbroot/u/dlb-1.2.3.zip` --- allows you to keep a certain version of dlb in your project's repository
independent of a system-wide installed version.

If you do not need the command-line utility :ref:`dlb <dlbexe>`, dlb does not even have to be installed (globally)
to build your project.


PyCharm integration
-------------------

If you use `PyCharm`_ to edit (and/or run and debug) your :term:`dlb scripts <script>` you can take advantage
of the integrated referral to external HTML documentation: Place the caret in the editor on a dlb object
(anything except a module) --- e.g. between the ``P`` and the ``a`` of ``dlb.fs.Path`` ---
and press :kbd:`Shift+F1` or :kbd:`Ctrl+Q` to show the HTML documentation in you web browser.

Configuration (as of PyCharm 2019.3):
Add the following documentation URLs in the dialog :menuselection:`Tool --> External Documentation`:

+-------------------+---------------------------------------------------------------------------------+
| Module Name       | URL/Path Pattern                                                                |
+===================+=================================================================================+
| ``dlb``           | :file:`https://dlb.readthedocs.io/en/{<which>}/reference.html#{element.qname}`  |
+-------------------+---------------------------------------------------------------------------------+
| ``dlb_contrib``   | :file:`https://dlb.readthedocs.io/en/{<which>}/reference.html#{element.qname}`  |
+-------------------+---------------------------------------------------------------------------------+

Replace *<which>* by a specific version like ``v0.3.0`` or ``stable`` for the latest version.


.. _PyCharm: https://www.jetbrains.com/pycharm/


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
  This would be error-prone and inefficient.
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


.. _`example/c-minimal/`: https://github.com/dlu-ch/dlb/tree/master/example/c-minimal/
.. _`example/c-gtk/`: https://github.com/dlu-ch/dlb/tree/master/example/c-gtk/


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

.. [#dependenciesoutsideworkingtree1]
   This is a deliberate design decision.
   It avoids complicated assumptions related to the :term:`mtimes <mtime>` of different filesystems,
   helps to promote a clean structure of project files and makes it possible to move an entire
   :term:`working tree` without changing the meaning of the :term:`run-database` in an unpredictable manner.
