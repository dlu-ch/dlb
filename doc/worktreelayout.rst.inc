.. _dlb-ex-workingtree-layout:

Layout of working tree
======================

The directory :file:`.dlbroot/` is mandatory --- it marks its parent directory as the root of a dlb working tree.
Everything else is optional. dlb does never touch filesystem objects outside :file:`.dlbroot/` unless
explicitly directed by a :term:`script` to do so.

The directory :file:`.dlbroot/u/` is optional. dlb never touches its content.
Each regular file or a symbolic links to a regular file in :file:`.dlbroot/u/` whose name ends in :file:`.zip` should
be a zip archive loadable by :mod:`zipimport`.
You can place dlb as :file:`.dlbroot/u/dlb.zip` in this directory (under version control). This makes the
working tree almost self-contained; only an external Python interpreter is needed.

The file or directory :file:`.dlbroot/z` is optional. dlb never touches it.

If you use Git for version control which does not support empty directories, add :file:`.dlbroot/z`
or any file in :file:`.dlbroot/u/`.

The lines marked with ``*`` show filesystem objects only given as an example.

**Before** first run of a dlb script:

::

   .dlbroot/
   src/                    *
      a.c                  *
      a.h                  *
      b.c                  *
   test/                   *
   ...

**During** a run of a dlb script:

::

   .dlbroot/
       o                   empty regular file, used to probe the "current" mtime
       runs-*.sqlite       run-database
       t/                  temporary files
           a               *
           b               *
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
       runs-*.sqlite       run-database
    src/                   *
      a.c                  *
      a.h                  *
      b.c                  *
    test/                  *
    out/                   *
      a.c.o                *
      b.c.o                *
    dist/                  *
      p                    *
    ...
