.. dlb documentation master file

dlb - explicit is better than implicit
======================================

dlb is a `Pythonic`_ build tool which does not try to mimic Make_, but brings the benefits of object-oriented languages
to the build process.

It is inspired by `djb's redo`_, but takes a more dynamic approach.

A build system *generates files* in a filesystem, mostly with the help of *external tools*.
Its most important tasks (and therefore of the writer of the build system's configuration files) are:

- collect and transform filesystem paths
- call tool binaries (e.g. compilers) with context-dependent command line arguments
- generate files (e.g. some program source files or configuration files)
- make the build fast by omitting unnecessary redos
- control the build by command line arguments

That's the areas where dlb wants to be strong - all this in a precisely specified way, with emphasis on correctness,
reliability and robustness.

dlb does not try to hide its Python personality.
Instead dlb build scripts are just Python scripts importing the :mod:`dlb` module and using its functionality.
There is no magic code before or after the script.

Since dlb build scripts are Python scripts, you can easily analyse, run or debug them in your favorite Python IDE.

Tools (e.g. compiler/linker toolchains) are represented as classes. Adapting tools means adapting classes
(by subclassing).

Example::

    import dlb.fs
    import dlb.cmd
    ...

    class Path(dlb.fs.PosixPath, dlb.fs.WindowsPath, dlb.fs.NonSpacePath): pass   # (a)

    class Compiler(CppCompilerGcc): WARNINGS = ['all']                            # (b)
    class Linker(StaticLinkerGcc): pass

    with dlb.cmd.Context():                                                       # (c)

        object_files = [                                                          # (d)
           Compiler(
               source_file=p,
               object_file=Path('build/out/' + p.as_string() + '.o')
           ).run().object_file
           for p in Path('src/X/').list(name_filter=r'.+\.cpp') if not p.is_dir()
        ]

        linker = Linker(
            object_files=object_files,
            linked_file=Path('build/out/example')                                 # (e)
        ).run()

        print('Size:', linker.linked_file.native.stat().st_size, 'B')             # (f)

Explanation:

a.  *Restrict paths* to ones without spaces, usable on Windows and Posix systems.
    The attempt to construct such a ``Path`` object for a path violating these restrictions leads to an exception
    (helps to enforce portability).

#.  *Configure* some tools of the toolchain by subclassing and redefining attributes.

#.  Create a *context*. A context describes how subprocesses (e.g. of the compiler) are executed and how
    diagnostic messages are handled.

#.  *Compile* all ``.cpp`` files in directory ``src/X/`` and its subdirectories into object files.

    Compiling also means: automatically find all included files and remember them as input dependencies for future
    runs of dlb.
    ``run()`` executes the compiler only when :term:`redo` is necessary (e.g. because one of its include files
    has changed). Otherwise is does almost nothing.

#.  *Link* these object files into an executable file.

#.  Output the *size of the executable file*.

Content
=======

.. toctree::
   :maxdepth: 2

   usage.rst
   terms.rst
   toplevelspec.rst
   fs_path.rst
   cmd_context.rst
   cmd_tool.rst
   cmd_tmpl.rst
   diagnostics.rst
   similar_tools.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _Make: https://en.wikipedia.org/wiki/Make_%28software%29
.. _`djb's redo`: https://cr.yp.to/redo.html
.. _`Pythonic`: https://www.python.org/dev/peps/pep-0020/
