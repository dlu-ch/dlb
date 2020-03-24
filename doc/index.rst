.. dlb documentation master file

dlb - explicit is better than implicit
======================================

dlb is a `Pythonic`_ `build tool <https://en.wikipedia.org/wiki/Build_tool>`_ that does not try to mimic Make_,
but brings the benefits of object-oriented languages to the build process.

It is inspired by `djb's redo`_, but takes a more dynamic approach.

A build system *generates files* in a filesystem, mostly with the help of *external tools*.
Its most important tasks are:

- collect and transform filesystem paths
- find and execute tool executables (e.g. compilers) with context-dependent command line arguments
- generate files (e.g. some program source files or configuration files)
- make the build fast by omitting unnecessary redos

These are the areas where dlb wants to be strong - all this in a precisely specified way, with emphasis on correctness,
reliability and robustness.

dlb does not try to hide its Python personality.
Instead dlb build scripts are just Python scripts importing the :mod:`dlb` module and using its functionality.
There is no magic code before or after the script.
Since dlb build scripts are Python scripts, you can easily analyse, run or debug them in your favorite Python IDE.

Tools (e.g. compiler/linker toolchains) are represented as classes. Adapting tools means adapting classes
by subclassing.

Example::

   import dlb.fs
   import dlb.ex
   ...

   class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath, dlb.fs.NonSpacePath): pass   # (a)

   class Compiler(CplusplusCompilerGcc): DIALECT = 'c++14'                       # (b)
   class Linker(CplusplusLinkerGcc): pass

   with dlb.ex.Context():                                                        # (c)
       output_path = Path('build/out/')

       object_files = [                                                          # (d)
          Compiler(
              source_file=p,
              object_file=output_path / p.with_appended_suffix('.o')
          ).run().object_file
          for p in Path('src/X/').list(name_filter=r'.+\.cpp') if not p.is_dir()
       ]

       application_file = Linker(
           object_and_archive_files=object_files,
           linked_file=output_path / 'example'                                   # (e)
       ).run().linked_file

       dlb.di.inform(f'size: {application_file.native.raw.stat().st_size} B')    # (f)

Explanation:

a. *Restrict paths* to ones without spaces, usable on Windows and Posix systems.
   The attempt to construct such a ``Path`` object for a path violating these restrictions leads to an exception
   (helps to enforce portability).

#. *Configure* some tools of the toolchain by subclassing and redefining attributes.

#. Create a *context*. A context describes how subprocesses (e.g. of the compiler) are executed and how
   diagnostic messages are handled.

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
   :maxdepth: 2

   usage.rst
   terms.rst
   toplevelspec.rst
   ex_context.rst
   ex_tool.rst
   fs.rst
   di.rst
   faq.rst
   similar_tools.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _Make: https://en.wikipedia.org/wiki/Make_%28software%29
.. _`djb's redo`: https://cr.yp.to/redo.html
.. _`Pythonic`: https://www.python.org/dev/peps/pep-0020/
