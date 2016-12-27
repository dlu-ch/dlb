:mod:`dlb.fs` --- Filesystem paths
==================================
.. module:: dlb.fs
   :synopsis: Filesystem paths

This module provides classes to represent and access filesystem objects in a save and platform-independent manner,
most prominently :class:`dlb.fs.Path` and its subclasses.

.. inheritance-diagram:: dlb.fs.Path dlb.fs.RelativePath dlb.fs.AbsolutePath dlb.fs.NoSpacePath dlb.fs.PosixPath dlb.fs.PortablePosixPath dlb.fs.PortableWindowsPath dlb.fs.WindowsPath dlb.fs.PortablePath


Path Objects
------------

.. class:: Path

   A :class:`dlb.fs.Path` represents the path of a filesystem object in a platform-independent manner and
   expresses whether the object is a directory or not.
   All operations on instances of :class:`dlb.fs.Path` show the same behaviour on every platform
   (with the exception of :attr:`native`).
   Its instances are immutable and hashable (they can be used in sets or as keys in dictionaries).

   All represented paths are either absolute or relative to the working directory of a process.

   The interface is similar to :mod:`pathlib` and conversion from and to ``pathlib`` paths is supported.

   If the path represented by a :class:`dlb.fs.Path` is meaningful as a concrete path on the platform the code
   is running on, :attr:`native` returns it in the form of a :class:`dlb.fs.Path.Native` instance, which can
   then be used to access the filesystem (like a :class:`pathlib.Path`).

   On all platform the following properties hold:

   - ``'/'`` is used as a path component separator.
   - Paths are absolute iff they start with ``'/'``.
   - A component ``'..'`` means the parent directory of the path before it.
   - A component ``'.'`` means the directory of the path before it;
     a non-empty path with all such components removed is equivalent to the original one.
   - A sequence of two or more consequent ``'/'`` is equivalent to a single ``'/'``, except at the beginning of
     the path.
   - At the beginning of the path:
       - Three or more consequent ``'/'`` are equivalent to a single ``'/'``
       - Exactly two consequent ``'/'`` (followed be a character other than ``'/'``) means that the following component
         is to be interpreted in a implementation-defined manner (e.g. `ISO 1003.1-2008`_ or UNC paths)
   - If the platform supports symbolic links, it resolves them as specified in `ISO 1003.1-2008`_
     (which means that ``'..'`` cannot be collapsed without knowing the filesystem's content).

   :class:`dlb.fs.Path` instances are comparable with each other by ``=``, ``<`` etc.
   They are also comparable with strings and :class:`pathlib.PurePath`.
   Comparison is done case-sensitively and component-wise, observing the equivalence relations described below.
   A directory path is considered smaller than a non-directory path, if both are otherwise identical.

   Usage example::

       p = dlb.fs.PortablePath('a/b/c/') / 'x/y'

       p.relative_to(...)

       ... = str(p.native)

       with p.native.open() as f:
           f.readline()

   The :class:`Path` class supports the following methods and attributes:

   .. method:: Path(path[, is_dir=None])

      Constructs a path from an other path or a string.

      If ``path`` is interpreted as a string representation of a path in Posix style with ``/`` as a component
      separator.
      It must not by empty and must be either absolute or relative.

      If `is_dir` is ``None``, the ending of ``path`` determines whether is considered a directory path or not;
      it is if it ends with ``'/'`` or a ``'.'`` or ``'..'`` component.

      If `is_dir` is ``True``, the path is considered a directory path irrespective of ``path``.

      If `is_dir` is ``False``, the path is considered a non-directory path irrespective of ``path``
      However, if ``path`` represents ``'.'`` or endwith a ``'..'`` component, a ``ValueError`` exception is raised.

      :type path: str | :class:`Path` | :class:`pathlib.PurePath`
      :type is_dir: NoneType | bool

      :raises TypeError: if ``path`` is neither a string nor a path
      :raises ValueError: if ``path`` is an empty string
      :raises ValueError: if ``path`` is a :class:`pathlib.PurePath` which is neither absolute nor relative

      Example::

          >>> p = Path('a/b/').is_dir()
          True

          >>> p = Path(pathlib.PureWindowsPath('C:\\Windows'), is_dir=True)
          >>> p
          Path('/C:/Windows/')
          >>> p.is_dir()
          True

          >>> p = Path('x/y/..', is_dir=False)
          Traceback (most recent call last):
          ...
          ValueError: cannot be the path of a non-directory: 'x/y/..'

   .. method:: is_dir()

      :return: ``True`` iff this represents the path of a directory.
      :rtype: bool

   .. method:: is_absolute()

      :return: ``True`` iff this represents an absolute path.
      :rtype: bool

   .. attribute:: parts

      A tuple giving access to the path’s various components::

           >>> p = Path('/usr/bin/python3')
           >>> p.parts
           ('/', 'usr', 'bin', 'python3')

      :rtype: tuple(str)

   .. attribute:: native

      This path as a native path.
      Use this to access the filesystem::

          p = Path('/usr/bin/')
          with open(p.native) as f:
             ...

      This attribute cannot be written.

      :rtype: :class:`Path.Native`

      :raises ValueError: if this path is not representable as :class:`Path.Native`

   .. attribute:: pure_posix

      This path as a :class:`pathlib.PurePosixPath`::

          >>> p = Path('/usr/bin/')
          >>> p.pure_posix
          PurePosixPath('/usr/bin')

      This attribute cannot be written.

      :rtype: :class:`pathlib.PurePosixPath`

   .. attribute:: pure_windows

      This path as a :class:`pathlib.PureWindowsPath`::

          >>> p = Path('/C:/Program Files/')
          >>> p.pure_windows
          PureWindowsPath('C:/Program Files')

      This attribute cannot be written.

      :rtype: :class:`pathlib.PureWindowsPath`


.. class:: Path.Native

   A native path whose instances can be used like once from :class:`pathlib.Path`.

   For each subclass ``P`` of :class:`dlb.fs.Path` there is a corresponding subclass ``P.Native`` which imposes the same
   restrictions as ``P``.
   If ``Q`` is a subclass of ``P`` and ``P`` is a subclass of :class:`dlb.fs.Path`, then ``Q.Native`` is a subclass
   of ``P.Native``.

   Example (on a Posix system)::

      >>> dlb.fs.NoSpacePath.Native('/tmp/x y')
      Traceback (most recent call last):
      ...
      ValueError: invalid path for 'NoSpacePath': '/tmp/x y' (must not contain space)

   In contrast to :class:`pathlib.Path`, conversion to string is done in a safe way:
   relative paths are guaranteed to start with ``'.'``.

   Example (on a Posix system)::

       >>> str(Path.Native('-rf'))
       './-rf'


Restricting Paths
-----------------

By subclassing :class:`dlb.fs.Path`, additional restrictions to the set of value values can be imposed
(trying to construct a :class:`dlb.fs.Path` from an invalid value raises an ``ValueError`` exception).
A subclass of :class:`dlb.fs.Path` should implement only :meth:`check_restriction_to_base`.

.. inheritance-diagram:: dlb.fs.Path dlb.fs.RelativePath dlb.fs.AbsolutePath dlb.fs.NoSpacePath dlb.fs.PosixPath dlb.fs.PortablePosixPath dlb.fs.PortableWindowsPath dlb.fs.WindowsPath dlb.fs.PortablePath

.. class:: RelativePath

   A :class:`dlb.fs.Path` which represents a relative path.

.. class:: AbsolutePath

   A :class:`dlb.fs.Path` which represents an absolute path.

.. class:: NoSpacePath

   A :class:`dlb.fs.Path` whose components do not contain ``' '``.

.. class:: PosixPath

   A :class:`dlb.fs.Path` which represents a POSIX-compliant (`ISO 1003.1-2008`_) paths in its least-constricted form.

   Every non-empty string, which does not contain ``'/'`` is a valid component.
   Components are separated by ``'/'``.
   '/' and every string of the form ``'//'`` ... ``'/'``, where ... is non-empty and does not contain ``'/'``
   is a valid root component.

   For every path prefix (in the POSIX sense) *{NAME_MAX}* and *{PATH_MAX}* are considered unlimited.

   Relevant parts of `ISO 1003.1-2008`_:

   - section 4.12 Pathname Resolution
   - section 4.5 File Hierarchy
   - section 4.6 Filenames
   - section 4.7 Filename Portability
   - section 3.267 Pathname
   - section 3.269 Path Prefix
   - limits.h

.. class:: PortablePosixPath

   A :class:`dlb.fs.PosixPath` which represents a POSIX-compliant (`ISO 1003.1-2008`_) path in its strictest form.
   Any path whose support is not required by POSIX or is declared as non-portable is considered invalid.

   A component cannot be longer than 14 characters, which must all be members of the
   *Portable Filename Character Set*.

   The length of the string representation of the path is limited to 255 characters.

   No absolute path prefix other than ``'/'`` is allowed (because implementation-defined).

.. class:: WindowsPath

   A :class:`dlb.fs.Path` which represents a Microsoft Windows-compliant path in its least-constricted form,
   which is either relative or absolute and does not contain components with reserved names (like ``NUL``).
   It cannot represent incomplete paths which are neither absolute nor relative to the current working
   directory (e.g. ``C:a\b`` and ``\\name``).

.. class:: PortableWindowsPath

   A :class:`dlb.fs.WindowsPath` which represents a Microsoft Windows-compliant path in its strictest form.

   A component cannot be longer than 255 characters.
   The path cannot not be longer than 259 characters.

.. class:: PortablePath

.. _POSIX:
.. _ISO 1003.1-2008: http://pubs.opengroup.org/onlinepubs/9699919799/basedefs/contents.html
