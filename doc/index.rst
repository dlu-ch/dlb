.. dlb documentation master file

dlb --- explicit is better than implicit
========================================

dlb is a `Pythonic`_ `build tool <https://en.wikipedia.org/wiki/Build_tool>`_ that does not try to mimic Make_
but to leverage the power of object-oriented languages. It is `free software`_.

dlb is inspired by `djb's redo`_ but takes a more dynamic approach.

A build system *generates files* in a filesystem, mostly with the help of *external tools*.
Its most important tasks are:

- collect and transform filesystem paths
- find and execute tool executables (e.g. compilers) with context-dependent command line arguments
- generate files (e.g. some program source files or configuration files)
- make the build fast by omitting unnecessary redos

These are the strengths of dlb.
dlb performs its tasks in a precisely specified way and with emphasis on correctness, reliability, and robustness.

dlb does not try to hide its Python personality.
dlb build scripts are just Python scripts importing the :mod:`dlb` module and using its functionality.
There is no magic code before or after the script.
Since dlb build scripts are Python scripts, you can easily analyse, run, or debug them in your favorite Python IDE.

Tools (e.g. compiler/linker toolchains) are represented as classes. Adapting tools means adapting classes
by subclassing.

Example::

   import dlb.di
   import dlb.fs
   import dlb.ex
   import dlb_contrib.gcc

   class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath, dlb.fs.NoSpacePath): pass    # (a)

   class Compiler(dlb_contrib.gcc.CplusplusCompilerGcc): DIALECT = 'c++14'       # (b)
   class Linker(dlb_contrib.gcc.CplusplusLinkerGcc): pass

   with dlb.ex.Context():                                                        # (c)
       output_directory = Path('build/out/')

       object_files = [                                                          # (d)
          Compiler(
              source_files=[p],
              object_files=[output_directory / p.with_appended_suffix('.o')]
          ).run().object_files[0]
          for p in Path('src/X/').iterdir(name_filter=r'.+\.cpp', is_dir=False)
       ]

       application_file = Linker(
           object_and_archive_files=object_files,
           linked_file=output_directory / 'example'                              # (e)
       ).run().linked_file

   dlb.di.inform(f'size: {application_file.native.raw.stat().st_size} B')        # (f)

Explanation:

a. *Restrict paths* to ones without spaces, usable on Windows and Posix systems.
   The attempt to construct such a ``Path`` object for a path violating these restrictions leads to an exception
   (helps to enforce portability).

#. *Configure* some tools of the toolchain by subclassing and redefining attributes.

#. Create a *context*. A context determines how subprocesses (e.g. of the compiler) are executed.

#. *Compile* all :file:`.cpp` files in directory :file:`src/X/` and its subdirectories into object files.

   Compiling also means: automatically find all included files and remember them as input dependencies for future
   runs of dlb.
   ``run()`` executes the compiler only when a :term:`redo` is necessary (e.g. because one of its include files
   has changed). Otherwise is does almost nothing.

#. *Link* these object files into an executable file.

#. Output the *size of the executable file*.

Content
=======

.. toctree::
   :maxdepth: 3

   faq.rst
   usage.rst
   reference.rst


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`

.. _Make: https://en.wikipedia.org/wiki/Make_%28software%29
.. _`djb's redo`: https://cr.yp.to/redo.html
.. _Pythonic: https://www.python.org/dev/peps/pep-0020/
.. _`free software`: https://www.gnu.org/philosophy/free-sw.en.html
