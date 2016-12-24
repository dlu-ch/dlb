:mod:`dlb.fs` --- Filesystem Paths
==================================

A :class:`dlb.fs.Path` represents the path of a filesystem object in platform-independent manner and
expressed whether the object is a directory or not.

The interface is similar to ``pathlib`` and conversion from an to ``pathlib`` paths is supported.

All represented paths are either absolute or relative to the working directory of a process.

On all platform the following assumptions are made:

  - ``'/'`` is used as a path component separator.
  - paths are absolute iff they start with ``'/'``.
  - A sequence of two or more consequent ``'/'`` are equivalent to a single ``'/'``, except at the beginning of the path.
  - At the beginning of the path:
      - three or more consequent ``'/'`` are equivalent to a single ``'/'``
      - exactly two consequent ``'/'`` (followed be a character other than ``'/'``) means that the following component
        is to be interpreted in a implementation-defined manner (e.g. `ISO 1003.1-2008`_ or UNC paths)
  - The platform resolving symbolic links according to `ISO 1003.1-2008`_ (which means that ``'..'`` cannot be collapsed
    without known the filesystem's content).

By subclassing :class:`dlb.fs.Path`, additional restrictions to the set of value values can be imposed
(trying to construct a :class:`dlb.fs.Path` from an invalid value raises an ``ValueError`` exception).
A subclass of :class:`dlb.fs.Path` should implement only :meth:`check_restriction_to_base`.

.. inheritance-diagram:: dlb.fs.Path dlb.fs.RelativePath dlb.fs.AbsolutePath dlb.fs.NoSpacePath dlb.fs.PosixPath dlb.fs.PortablePosixPath dlb.fs.PortableWindowsPath dlb.fs.WindowsPath dlb.fs.PortablePath

For each subclass ``P`` of :class:`dlb.fs.Path` there is a corresponding subclass ``P.Native`` which imposes the same
restrictions as ``P``.
If ``Q`` is a subclass of ``P`` and ``P`` is a subclass of :class:`dlb.fs.Path`, then ``Q.Native`` is a subclass
of ``P.Native``.
These ``Native`` classes can be used like ``pathlib.Path`` to access the filesystem.

When comparing:

  - Paths are compared case-sensitively.
  - Directory < non-directory

Example::

    p = dlb.fs.PortablePath('a/b/c/') / 'x/y'

    p.relative_to(...)

    ... = str(p.native)

    with p.native.open() as f:
        f.readline()


Module Contents
---------------

.. automodule:: dlb.fs
   :synopsis: Filesystem paths.
   :members:
   :special-members:
   :exclude-members: __weakref__

.. _POSIX:
.. _ISO 1003.1-2008: http://pubs.opengroup.org/onlinepubs/9699919799/basedefs/contents.html
