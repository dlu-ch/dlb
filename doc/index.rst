.. dlb documentation master file

dlb - explicit is better than implicit
======================================

dlb is a `Pythonic <https://www.python.org/dev/peps/pep-0020/>`_ build tool which does not try to mimic Make_,
but brings the benefits of object-oriented languages to the build process.
It is inspired by `djb's redo <https://cr.yp.to/redo.html>`_.

The most important task of a build system (and therefore of the writer of the build system's configuration files) are:

- collect and transform filesystem paths
- call tool binaries (e.g. compilers) with context-dependent command line arguments
- generate files (e.g. some program source files or configuration files)
- make the build fast by omitting unnecessary redos
- control the build by command line arguments

That's the areas where dlb wants to be strong.

dlb does not try to hide its Python personality.
Instead dlb build scripts are just Python scripts importing the ``dlb`` module and using its functionality.
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
           ).run_in_context().object_file
           for p in Path('src/X/').list(name_filter=r'.+\.cpp') if not p.is_dir()
        ]

        linker = Linker(
            object_files=object_files,
            linked_file=Path('build/out/example')                                 # (e)
        ).run_in_context()

        print('Size:', linker.linked_file.native.stat().st_size, 'B')             # (f)

Explanation:

a.  Restrict paths to ones without spaces, usable on Windows and Posix systems.
    The attempt to construct such a ``Path`` object for a path violating these restrictions leads to an exception.

    This is useful to enforce portability where necessary.

#.  Configure some tools of the toolchain by subclassing and redefining attributes.

#.  Create a context object.

    A context object describes how subprocesses (e.g. the compiler) are started.
    It also stores the state of inputs and outputs, which are used to determine
    whether a run is necessary or not.

#.  Compile all ``.cpp`` files in directory ``src/X/`` and its subdirectories into object files.

    Compiling also means: automatically find all included files and store them as inputs for future executions.
    ``run_in_context()`` runs the compiler only if not all outputs exist or if an input, the tool or the context
    has changed.

#.  Link these object files into an executable file.

#.  Output the size of the executable file.

.. _Make: https://en.wikipedia.org/wiki/Make_%28software%29

Content
=======

.. toctree::
   :maxdepth: 2

   fs_path.rst
   cmd_tmpl.rst
   cmd_tool.rst
   similar_tools.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

