Usage
=====

Installation
------------

dlb is written in `Python`_ and requires at least Python 3.7.

The canonical way to install dlb is from the Python Package Index (`PyPI`_)::

   $ python3 -m pip install dlb

If you prefer not to install to the Python system location or do not have privileges to do so, you can add a flag to
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
See :ref:`here <usage-self-contained-project>` for details.


Update and uninstall
--------------------

Update an dlb installation with::

   $ python3 -m pip install --upgrade [ --user ] dlb

Uninstall it with::

   $ python3 -m pip uninstall [ --user ] dlb


A simple project
----------------

We assume that you want to build some software from a `Git`_ repository with dlb and a `POSIX`_ compliant shell
on a GNU/Linux system.

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
file or directories outside :file:`.dlbroot` (see :ref:`here <dlb-ex-workingtree-layout>` for details on the
directory layout).
We will use a :term:`dlb script <script>` called :file:`build.py` to build our project, so let's start with an
polite one::

   $ echo 'print("hello there!")' > build.py


Run dlb
^^^^^^^

Now, we can use :file:`dlb` to run :file:`build.py`::

   $ dlb build
   hello there!

We could also have used ``python3 "${PWD}"/build.py`` instead of ``dlb build``. ``dlb`` comes in handy when you are
working in a subdirectory of the :term:`working tree` or when you need modules from ZIP archives
(e.g. :ref:`dlb itself <usage-self-contained-project>`)::

   $ mkdir src
   $ cd src
   $ dlb
   using arguments of last successful run: 'build.py'
   hello there!
   $ cd ..

See ``dlb --help`` (or :ref:`here <dlbexe>`) for a detailed description of ``dlb``.

The effect of ``dlb`` - with or without parameters - is independent of the current working directory
(as long as the current working directory is inside the working tree).
This allows to define convenience shell aliases for projects that use multiple dlb scripts with lengthy script names
or command line arguments.

Example (Bash): ``alias b='dlb build-description/prepare-env --no-doc'``.


Execute a custom tool in an execution context
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Replace the content of :file:`build.py` with this::

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
       t.start()  # start running the tool instance in the active execution context

   dlb.di.inform('finished successfully')

This defines a :term:`tool` called ``Replacer`` with an *input dependency role* ``template_file`` and an *output
dependency role* ``output_file``. The class attributes ``PATTERN`` and ``REPLACEMENT`` are *execution parameters* of the
tool. The method ``redo()`` is called by ``t.start()`` eventually if a :term:`redo` is necessary.

Create a file :file:`src/main.c.tmpl` with this content::

   // xxx
   #include <stdio.h>

   int main() {
       printf("xxx\n");
       return 0;
   }

When you run ``dlb`` now, you get something like this::

   $ dlb build
   D check redo necessity for tool instance 1... [+0.000000s]
     D explicit output dependencies... [+0.000161s]
       I redo necessary because of filesystem object: 'build/out/main.c'
         | reason: [Errno 2] No such file or directory: '/.../hello/build/out/main.c'
       D done. [+0.000264s]
     D done. [+0.000331s]
   I start redo for tool instance 1 [+0.014796s]
   I replaced regular file with different one: 'build/out/main.c'
   I finished successfully

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
   I finished successfully

Nothing happens because the output existed and the input (including the tool definition in :file:`build.py`)
did not change. After a modification of the input dependency, dlb again causes a redo::

   $ touch src/main.c.tmpl
   $ dlb build
   D check redo necessity for tool instance 1... [+0.000000s]
     D compare input dependencies with state before last successful redo... [+0.000287s]
       I redo necessary because of filesystem object: 'src/main.c.tmpl'
         | reason: mtime has changed
       D done. [+0.000375s]
     D done. [+0.000385s]
   I start redo for tool instance 1 [+0.014572s]
   I replaced regular file with different one: 'build/out/main.c'
   I finished successfully


Control the diagnostic message verbosity
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

It is good practice to output some summary of a successful build even if no redo was necessary.
This can be a relevant information on the most important build product (e.g. code size of an application)
or just the line ``dlb.di.inform('finished successfully')`` at the end of the dlb script.

In case you find the standard Python traceback (output on uncaught exceptions) too verbose or cluttered,
you can replace it by the one provided by :mod:`dlb_contrib.exctrace`.


Commit the changes
^^^^^^^^^^^^^^^^^^

Git does not track empty directories. If we want Git to create :file:`.dlbroot` as part of the repository, a file
must be added. We :ref:`can use <dlb-ex-workingtree-layout>` an empty file :file:`.dlbroot/z` to that end::

   $ touch .dlbroot/z
   $ echo /.dlbroot/ > .gitignore
   $ git add .gitignore
   $ git add -f .dlbroot/z
   $ git add ...
   $ git commit


Understand redo necessity
^^^^^^^^^^^^^^^^^^^^^^^^^

Everything related to dependency checking and :term:`redos <redo>` is centered around
:term:`tool instances <tool instance>`; only tool instances can have dependencies.

This line creates a tool instance *t* that assigns the concrete input dependency ``dlb.fs.Path('src/main.c.tmpl')`` to
the input dependency role ``template_file`` and the concrete output dependency ``dlb.fs.Path('build/out/main.c')`` to
the output dependency role ``output_file``::

   t = Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c')

``t.start()`` performs a redo when

a. one is explicitly requested by ``t.start(force_redo=True)`` or
b. a redo is considered necessary (see :term:`here <redo necessity>` for general conditions and the documentation of
   the dependency classes for the specific ones).

.. note::
   In contrast to what someone used to the appearance of SCons scripts might expect, the constructor of a tool instance
   does not run it. Make sure you call ``start()`` on a tool instance when you want it to perform its actual task.

After the successful completion of a redo of a tool instance *t* the :term:`run-database` contains the depended-upon
state of its (explicit and non-explicit) input dependencies before the start of the redo and its non-explicit
input dependencies.

A redo of *t* from above is considered necessary if at least one of the following conditions is true:

- A redo was never performed successfully before for *t* (same class and fingerprint) according to the
  :term:`run-database`.
- :file:`build/out/main.c` does not exist as a regular file.
- The :term:`mtime`, size, UID, GID, or set of filesystem permissions of :file:`src/main.c.tmpl` has changed since the
  start of the last known successful redo for *t* (because it is an output dependency of *t*)
- The value of ``PATTERN`` or ``REPLACEMENT`` has changed since the the last known successful redo for *t*.
- The :term:`mtime`, size, UID, GID, or set of filesystem permissions of :file:`build.py` has changed since the
  last known successful redo of *t* (because :file:`build.py` is a definition file for *t* in the :term:`managed tree`).

.. note::
   You may have noticed that an :term:`mtime` modification of :file:`build/out/main.c` does *not* lead to a redo.
   A modification of an output dependency is always treated as purposeful.
   This allows for modification of output dependencies after they were generated (e.g. for source code formatting
   or for small fixes in a huge set of generated HTML documents). [#noredoonoutputmodification1]_

Tool instances are identified by their class (file path and line number of definition) and their fingerprint.
The fingerprint includes the concrete dependencies of the tool instance which are defined by arguments of the
constructor matching class attributes, and its execution parameters.
Consider the following tool instances::

   t = Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c')  # from above
   t2 = Replacer(template_file=dlb.fs.Path('src/main.c.tmpl'), output_file='build/out/main.c')
   t3 = Replacer(template_file='src/MAIN.C.TMPL', output_file='build/out/main.c')

*t2* and *t* have the same same class and fingerprint and are therefore indistinguishable with respect to dependencies;
the statements ``t.start()`` and ``t2.start()`` have the same effect under all circumstances.
*t3* on the other hand has a different fingerprint; ``t3.start()`` does not affect the last known successful redo
for *t*.

.. note::
   dlb never stores the state of filesystem objects outside the :term:`working tree` in its :term:`run-database`.
   The modification of such a filesystem object does *not* lead to a redo.
   [#dependenciesoutsideworkingtree1]_


Understand redo concurrency
^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``t.start()`` "performs a redo" it schedules the eventual (asynchronous) execution of
:meth:`redo() <dlb.ex.Tool.redo>` and then returns immediately. The completion of the pending redo is left to
:mod:`asyncio`.

So, redos are parallel by default. The maximum number of pending redos at a time is given by
:attr:`max_parallel_redo_count <dlb.ex.Context.max_parallel_redo_count>` of the :term:`active context`.

In contrast to GNU Make or Ninja, for example, filesystem paths used in multiple tool instances do *not* form an
implicit mutual exclusion mechanism. Synchronization and ordering of events are explicit in dlb.
Redos can be synchronized

a) globally for all pending redos by the means of :term:`(execution) contexts <context>` or
b) selectively for a specific redo by accessing the result (proxy) object return by :meth:`dlb.ex.Tool.start()`.

See :meth:`dlb.ex.Tool.start()` for details.

As a rule, paths `should not be repeated <https://en.wikipedia.org/wiki/Don%27t_repeat_yourself>`_ like
:file:`build/out/main.c` in this snippet (which may execute the redos of ``Replacer(...)`` and ``CCompiler(...)``
in parallel)::

   Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c').start()
   CCompiler(source_files=['build/out/main.c'], object_files=['build/out/main.c.o']).start()

Better use a variable whose name expresses the meaning of the filesystem object or cascade tool instances with their
result objects. Write this, for example, if you want to express that one tool instance depends on the result of
another one::

   r = Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c').start()
   CCompiler(source_files=[r.output_file], object_files=['build/out/main.c.o']).start()
   # waits for pending redo with result r to complete before CCompiler(...).start()

This mechanism is used in :dlbrepo:`example/c-minimal/`.

To wait for the completion of a specific redo without referring to specific dependencies, you can use
``complete()`` instead::

   r = Replacer(...).start().complete()
   assert r.iscomplete
   # note: the missing '_' makes clear that 'complete' and 'iscomplete'
   # are not names of dependencies

Alternatively, you could wait for *all* pending redos to complete before ``Compiler(...).start()`` if you prefer
to split the build into sequential phases like this::

   # code generation phase
   Replacer(template_file='src/main.c.tmpl', output_file='build/out/main.c').start()

   # compilation phase
   with dlb.ex.Context():  # waits for all pending redos to complete
       CCompiler(source_files=['build/out/main.c'], object_files=['build/out/main.c.o']).start()

This mechanism is used in :dlbrepo:`example/c-gtk-doxygen/`.


Real stuff
^^^^^^^^^^

There are more meaningful tasks than replacing text in a text file.

For example, building a C program with GCC looks like
this: :dlbrepo:`example/c-minimal/build-all.py`.

The package :mod:`dlb_contrib` provides tools and utilities to build upon.


.. _usage-self-contained-project:

Self-contained projects: dlb as part of the repository
------------------------------------------------------

ZIP archives in :file:`.dlbroot/u/` are automatically added to the module search path of the Python interpreter
by :ref:`dlb <dlbexe>`. Placing the :mod:`dlb` package as a version controlled ZIP archive there
--- say, :file:`.dlbroot/u/dlb-1.2.3.zip` --- allows you to keep a certain version of dlb in your project's repository
independent of a system-wide installed version.

If you do not need the command-line utility :ref:`dlb <dlbexe>`, dlb does not even have to be installed (globally)
to build your project.


Redirection of diagnostic messages
----------------------------------

Diagnostic messages are output to :data:`sys.stderr` by default.
To unambiguously separate them from output of executed tools (e.g. compiler warnings) you can always set a destination
with :func:`dlb.di.set_output_file()`::

   import dlb.di
   dlb.di.set_output_file(open('run.log', 'w'))
   # any object with a file-like write() method can be used as output file

The following snippet "exposes" the destination of diagnostic messages to the parent process and therefore allows
for its manipulation by shell redirection::

   try:
       dlb.di.set_output_file(open(3, 'w', buffering=1))
   except OSError:  # e.g. because file descriptor 3 not opened by parent process
       pass

Possible applications (on a typical GNU/Linux system)::

   $ dlb 3>run.log             # write to file
   $ dlb 3>/dev/pts/0          # show in specific pseudo terminal
   $ dlb 3>&1 1>&2 | gedit -   # (incrementally) show in GEdit window

   $ mkfifo dlb.fifo
   $ tilix -e cat dlb.fifo && dlb 3>dlb.fifo  # show in new terminal emulator window

If you mostly work with a terminal emulator that is (at least partially) compliant with ISO/IEC 6429, colored output
might be useful which can easily be achieved with :class:`!MessageColorator` from :mod:`dlb_contrib.iso6429`.


PyCharm integration
-------------------

If you use `PyCharm`_ to edit (and/or run and debug), your :term:`dlb scripts <script>` you can take advantage
of the integrated referral to external HTML documentation: Place the caret in the editor on a dlb object
(anything except a module) --- e.g. between the ``P`` and the ``a`` of ``dlb.fs.Path`` ---
and press :kbd:`Shift+F1` or :kbd:`Ctrl+Q` to show the HTML documentation in your web browser.

Configuration (as of PyCharm 2020.1):
Add the following documentation URLs in the settings page :menuselection:`Tool --> External Documentation`:

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

These recommendations describe the typical use case.
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
  As long as the size of the modified regular file changes or the :term:`working tree time` is monotonic, there is no
  :term:`redo miss` in the current or in any future :term:`run of dlb`. [#managedtree1]_ [#make3]_

  However, many external tools cannot guarantee proper behaviour if some of their input files are changed while they
  are being executed (e.g. a compiler working on multiple input files).

- Avoid :command:`mv` to replace regular files; is does not update its target's :term:`mtime`.

  Use :command:`cp` instead.

- Be careful when you modify a file that is an input dependency of a :term:`tool instance` via ``mmap``. [#mmap1]_

- Do not put the system time used as :term:`working tree's system time` back *on purpose* while
  :term:`dlb is running <run of dlb>` or while you are modifying the :term:`managed tree`. [#workingtreetime]_


Write scripts and tools
^^^^^^^^^^^^^^^^^^^^^^^

- It is safe to modify the :term:`managed tree` immediately after a :term:`run of dlb` is completed (e.g. in the same
  :term:`script`) without risking a :term:`redo miss` [#make2]_

- Do not use (explicit) multithreading. Use :py:mod:`asyncio` instead.

- Do not use multiple hierarchical :term:`scripts <script>` (where one calls another).
  This would be error-prone and inefficient.
  Use scripts only on the top-level.

- Split large :term:`scripts<script>` into small modules that are imported by the script
  (like this: :dlbrepo:`example/c-gtk-doxygen/`).
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

- Do not modify the :term:`managed tree` in a :term:`script` -- e.g. by calling :func:`shutil.rmtree()` directly --
  unless you are sure no redo is pending that accesses the affected filesystem objects. [#managedtree1]_


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

.. [#noredoonoutputmodification1]
   It is impossible to reliably detect an :term:`mtime` modification of a (POSIX) filesystem object after its generation
   without the requirement of monotonic system time and real-time guarantees.
   Without such (unrealistic) requirements, the probability of correct detection can be made arbitrarily small by
   pausing the involved processes at the right moments.

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
