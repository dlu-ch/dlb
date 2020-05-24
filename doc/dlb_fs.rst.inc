:mod:`dlb.fs` --- Filesystem paths
==================================

.. module:: dlb.fs
   :synopsis: Filesystem paths

This module provides classes to represent and access filesystem objects in a safe and platform-independent manner,
most prominently :class:`dlb.fs.Path` and its subclasses.

The interface is similar to :mod:`pathlib`. :class:`dlb.fs.Path` is much faster than :class:`pathlib.PurePath`.
(Lossy) conversion from and to :mod:`pathlib` paths is supported.


Path objects
------------

.. class:: Path

   A :class:`dlb.fs.Path` represents the path of a filesystem object in a platform-independent manner and
   expresses whether the object is a directory or not.
   The represented path is called a directory path in the former case and a non-directory path in the latter case.

   All represented paths are either absolute or relative to some other path (usually the working directory
   of the running process).

   All operations on instances of :class:`dlb.fs.Path` show the same behaviour on every platform (with the exception of
   :attr:`native`). Its instances are immutable and hashable_ (they can be used in sets or as keys in dictionaries).

   If the path represented by a :class:`dlb.fs.Path` is meaningful as a concrete path on the platform the code
   is running on, :attr:`native` returns it in the form of a :class:`dlb.fs.Path.Native` instance, which can
   then be used to access the filesystem.

   On all platform the following properties hold:

   - A path does not contain ``'\0'`` (NUL).
   - A component ``'..'`` means the parent directory of the path before it.
   - A component ``'.'`` means the directory of the path before it.
   - If the platform supports symbolic links, it resolves them as specified in `ISO 1003.1-2008`_
     (which means that ``'..'`` cannot be collapsed without knowing the filesystem's content).
   - ``'/'`` is used as a path component separator.
   - A path is absolute if and only if it starts with ``'/'``.
     a non-empty path with all such components removed is equivalent to the original one.
   - A sequence of two or more consequent ``'/'`` is equivalent to a single ``'/'``, except at the beginning of
     the path.
   - At the beginning of the path:

     - Three or more consequent ``'/'`` are equivalent to a single ``'/'``
     - Exactly two consequent ``'/'`` (followed be a character other than ``'/'``) means that the following component
       is to be interpreted in a implementation-defined manner (e.g. `ISO 1003.1-2008`_ or UNC paths)

   :class:`dlb.fs.Path` instances are comparable with each other by ``==``, ``<`` et cetera which define a total
   ordering. Comparison is case-sensitive and component-wise. For two :class:`dlb.fs.Path` instances *p* and *q*:

   - ``p = q`` if and only if ``p.components == q.component and p.is_dir == q.is_dir``.
   - ``p < q`` if ``p.components < q.component``
     (a true prefix of a path is smaller than the prefixed path, and every relative path is smaller than every
     absolute path).
   - ``p < q`` if ``p.components == q.component and p.is_dir < q.is_dir``
     (a non-directory path is smaller than an otherwise equal directory path).

   Usage example::

      >>> p = dlb.fs.PortablePath('a/b/c/') / 'x/y'
      >>> p.relative_to('a/b/)
      PortablePath('c/x/y')

      >>> dlb.fs.Path('x/y/z.tar.gz')[:-2]
      Path('x/')

      >>> dlb.fs.Path('x/y/z.tar.gz').components[-1]
      'z.tar.gz'

   The :class:`dlb.fs.Path` class supports the following methods and attributes:

   .. method:: Path(path, *, is_dir=None)

      Construct a path from another path, string, or path component sequence:

      - If *path* is a string, it is interpreted as the string representation of a path in POSIX style with ``/`` as a
        component separator. It must not be empty.
      - If *path* is a sequence, it is interpreted as a path component sequence after all its members have been
        converted to str (see :attr:`components`).
      - If *path* is an instance of :class:`dlb.fs.Path`, it is copied. This is very fast..
      - If *path* is an instance of :class:`pathlib.PurePath` (including :class:`pathlib.Path`), it is interpreted
        according to its meaning expressed by the class (a :class:`pathlib.PureWindowsPath` instance is interpreted as
        an an MS Windows path, for example).
        If *path* is neither absolute nor relative, a :exc:`ValueError` exception is raised.
      - If *path* is an instance of :class:`dlb.fs.Path.Native`, its :class:`pathlib.Path` representation is used.
        :attr:`native` of the constructed path is equal to *path*.

      If *is_dir* is ``True``, the path is considered a directory path irrespective of ``path``.

      If *is_dir* is ``False``, the path is considered a non-directory path irrespective of ``path``.
      However, if *path* represents ``'.'`` or ends with a ``'..'`` component, a :exc:`ValueError` exception is raised.

      If *is_dir* is ``None``, the ending of *path* determines whether it is considered a directory path or not.
      If *path* is a string that ends with  ``'/'`` or if the last component of *path* is ``'.'`` or ``'..'`` component,
      it is considered a directory path.

      :param path: path object, portable string representation, or path component sequence
      :type path: str | :class:`dlb.fs.Path` | :class:`dlb.fs.Path.Native` | :class:`pathlib.PurePath` | sequence of str
      :param is_dir: ``True`` if this is a directory path, ``False`` if not and ``None`` for derivation from *path*
      :type is_dir: NoneType | bool

      :raises TypeError: if *path* is neither a path, string, nor path component sequence
      :raises ValueError: if *path* is an empty string
      :raises ValueError: if *path* cannot be represented by this (subclass of) :class:`dlb.fs.Path`
      :raises ValueError: if *path* is a :class:`pathlib.PurePath` which is neither absolute nor relative

      Examples::

         >>> p = dlb.fs.Path('a/b/').is_dir()
         True

         >>> p = dlb.fs.Path(pathlib.PureWindowsPath('C:\\Windows'), is_dir=True)
         >>> p
         Path('/C:/Windows/')
         >>> p.is_dir()
         True

         >>> p = dlb.fs.Path('x/y/..', is_dir=False)
         Traceback (most recent call last):
         ...
         ValueError: cannot be the path of a non-directory: 'x/y/..'

   .. method:: is_dir()

      :return: ``True`` if and only if this represents a directory path.
      :rtype: bool

   .. method:: is_absolute()

      .. in pathlib:
         pathlib.PurePath.is_absolute()

      :return: ``True`` if and only if this represents an absolute path.
      :rtype: bool

      .. note::
         While POSIX_ considers paths starting with exactly two ``'/'`` *not* as absolute paths,
         this class does (and so does :mod:`pathlib`).

   .. method:: is_normalized()

      .. in os.path:
         os.path.normpath(): "Normalize a pathname by collapsing [...]"

      :return:
        ``True`` if and only if this represents a :term:`normalized path` (without ``'..'`` components)
      :rtype: bool

   .. method:: relative_to(other, *, collapsable=False)

      .. in pathlib:
         pathlib.PurePath.relative_to()

      Return a version of this path relative to the directory path represented by ``C(other)`` where *C* is the class
      of this path.

      If *collapsable* is ``False``, this path must be a prefix of *other*.
      If *collapsable* is ``True``, *other* is treated as a :term:`collapsable path` and the minimum of necessary
      :file:`..` components is prepended.

      :param other: directory path
      :type other: :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from
      :param collapsable: is *other* a :term:`collapsable path`?
      :type collapsable: bool
      :return: relative path
      :rtype: class of this object

      :raises ValueError: if ``C(other)`` is not a directory path
      :raises ValueError: if one of this path and ``C(other)`` is a relative path and the other one is an absolute path
      :raises ValueError: if *collapsable* is ``False`` and this path is not a prefix of ``C(other)``

   .. method:: with_appended_suffix(suffix)

      Return a version of this path with *suffix* appended to its last component.

      :param suffix: suffix that does not change the meaning of the path
      :type suffix: str
      :rtype: class of this object

      :raises ValueError: if *suffix* is ``'.'`` or ``'..'`` or does contain ``'/'`` or ``'\0'`` (NUL)

   .. method:: as_string()

      The unique representation as a POSIX-style string.

      For every :class:`dlb.fs.Path` instance *p* and ``s = p.as_string()``, the following holds:

      - *s* is not empty
      - ``s[0]`` is ``'/'`` if and only if *p* is an absolute path
      - ``s[-1]`` is ``'/'`` if and only if *p* is a directory path
      - ``dlb.fs.Path(s) == p``

      :rtype: str

   .. method:: iterdir(*, name_filter='', is_dir=None, recurse_name_filter=None, follow_symlinks=True, cls=None)

      .. in pathlib:
         pathlib.Path.iterdir()

      Yield all path objects of the directory contents denoted by this path and matched by the
      name filters.
      The paths are duplicate-free and in a platform-independent and deterministic order but not necessarily sorted.
      Their class is the class of this object if *cls* is ``None`` and *cls* otherwise.

      The path *p* of an existing filesystem object is eventually yielded if and only if

      - its name matches the name filter *name_filter* and
      - *is_dir* is None or *is_dir* is ``False`` and *p* is a non-directory
        or *is_dir* is ``True`` and *p* is a directory
      - it is contained in a matched directory.

      A directory is a matched directory if and only if it is the directory *d* denoted by this path or a direct
      subdirectory of a matched directory whose name matches the name filter *recurse_name_filter*.
      If *follow_symlinks* is ``True``, a symbolic link to an existing directory is considered a direct subdirectory
      of the director containing the symbolic link.
      If *follow_symlinks* is ``False`` or the target of the symbolic link does not exist,
      it is considered a non-directory.

      *name_filter* and *recurse_name_filter* are *name filters*.
      A name filter can be

      - ``None`` --- no name matches this filter
      - a callable *c* accepting exactly one argument --- a name *n* matches this filter if and only if
        ``bool(c(n))`` is ``True``
      - a compiled regular expression *r* --- a name *n* matches this filter if and only if ``r.fullmatch(n))``
        is not ``None``
      - a non-empty regular expression string ``s``--- a name *n* matches this filter if and only if
        ``re.compile(s).fullmatch(n))`` is not ``None``
      - an empty string --- every name matches this filter

      Example::

         for p in dlb.fs.Path('src/').iterdir(name_filter=r'(?i).+\.cpp',
                                              recurse_name_filter=lambda n: '.' not in n):
             ...

      :rtype: *cls* | class of this object

      :raises TypeError: if *cls* is neither ``None`` nor a subclass of :class:`dlb.fs.Path`
      :raises TypeError: if *name_filter* or *recurse_name_filter* are not both name filters
      :raises ValueError: if this is a non-directory path

   .. method:: iterdir_r(*, name_filter='', is_dir=None, recurse_name_filter=None, follow_symlinks=True, cls=None)

      Like :meth:`iterdir`, but all yielded paths are relative to this path.

   .. method:: list(*, name_filter='', is_dir=None, recurse_name_filter=None, follow_symlinks=True, cls=None)

      Return all paths yielded by :meth:`iterdir` as a sorted list.

      Example::

         >>> dlb.fs.NoSpacePath('src/').list(name_filter=r'(?i).+\.cpp')
         [NoSpacePath('src/Clock.cpp'), NoSpacePath('src/main.cpp')]

   .. method:: list_r(*, name_filter='', is_dir=None, recurse_name_filter=None, follow_symlinks=True, cls=None)

      Return all paths yielded by :meth:`iterdir_r` as a sorted list.

      Example::

         >>> dlb.fs.NoSpacePath('src/').list(name_filter=r'(?i).+\.cpp')
         [NoSpacePath('Clock.cpp'), NoSpacePath('main.cpp')]

   .. method:: find_latest_mtime(*, name_filter='', is_dir=None, recurse_name_filter=None, \
                                 follow_symlinks=True, cls=None)

      Return the path of the filesystem object with the latest :term:`mtime` among all paths yielded by :meth:`iterdir`
      or ``None`` if there is no such path.

      If more than one filesystem object with a path yielded by :meth:`iterdir` has the same mtime, one of them is
      chosen in a platform-independent and deterministic manner.

   .. method:: propagate_mtime(*, name_filter='', is_dir=None, recurse_name_filter='')

      For each path yielded by :meth:`iterdir(..., follow_symlinks=False) <iterdir>` with an :term:`mtime`
      later than the mtime of its containing directory, update the mtime of the containing directory (and its parents up
      to and including this directory if the resulting mtime is later than their mtime).
      Return the resulting mtime of this directory in nanoseconds or ``None`` if it was not updated.

      .. note::
         In contrast to :meth:`iterdir` the default value for recurse_name_filter is ``''`` which means that
         by default no subdirectory is ignored.

   .. attribute:: components

      The path component sequence of this path as a tuple of strings.

      The first element is the root component. It is ``'/'`` or ``'//'`` if the path is absolute and ``''`` otherwise.
      All other elements are the path's non-root components.
      They do not contain ``'/'`` and are not ``'.'`` or ``'..'``.

      Example::

         >>> dlb.fs.Path('/usr/bin/python3').component
         ('/', 'usr', 'bin', 'python3')
         >>> dlb.fs.Path('x/y/').component
         ('', 'x', 'y')
         >>> dlb.fs.Path('.').component
         ('',)

      This attribute cannot be written.

      :rtype: tuple of str

   .. attribute:: parts

      .. in pathlib:
         pathlib.PurePath.parts

      The path component sequence of this path with an empty root-component removed::

         >>> dlb.fs.Path('/usr/bin/python3').parts
         ('/', 'usr', 'bin', 'python3')
         >>> dlb.fs.Path('x/y/').parts
         ('x', 'y')
         >>> dlb.fs.Path('.').parts
         ()

      This attribute cannot be written.

      :rtype: tuple of str

   .. attribute:: native

      This path as a (non-portable) native path.

      Use it to access the filesystem::

         p = dlb.fs.Path('/usr/bin/')
         ... = os.stat(p.native)       # p.native is a os.PathLike
         ... = os.stat(str(p.native))
         ... = p.native.raw.stat()     # pathlib.Path (slower)

      .. note::
         Whether a path is a directory path can only by reconstructed from its native path if it ends with a ``'.'`` or
         ``'..'`` component.

      This attribute cannot be written.

      :rtype: :class:`.dlb.fs.Path.Native`

      :raises ValueError: if this path is not representable as :class:`Path.Native`

   .. attribute:: pure_posix

      .. in pathlib:
         pathlib.PurePath.as_posix()

      This path as a :class:`pathlib.PurePosixPath`::

         >>> dlb.fs.Path('/usr/bin/').pure_posix
         PurePosixPath('/usr/bin')

      This attribute cannot be written.

      :rtype: :class:`pathlib.PurePosixPath`

   .. attribute:: pure_windows

      This path as a :class:`pathlib.PureWindowsPath`::

         >>> Path('/C:/Program Files/').pure_windows
         PureWindowsPath('C:/Program Files')

      This attribute cannot be written.

      :rtype: :class:`pathlib.PureWindowsPath`

   .. describe:: path[key]

      Returns the path represented by a :attr:`path.parts[key] <parts>` where *key* is a slice of indices with
      a positive slice step.

      The resulting path is absolute (with the same root-component) if and only if the slice starts at 0 and *path*
      is an absolute path.

      The resulting path is a non-directory path if and only if it contains the last component and if *path* is a
      non-directory path.

      Raises :exc:`TypeError` if *key* is not a slice.
      Raises :exc:`ValueError` if *path* is an absolute path and *key* is an empty slice.

      Examples::

         >>> dlb.fs.Path('src/comp/lib/Core.cpp')[:-2]
         Path('src/comp/'

         >>> dlb.fs.Path('src/comp/..')[1:-1]
         Path('comp/')

   .. describe:: path / other

      .. in pathlib:
         pathlib.PurePath.__truediv__
         pathlib.PurePath.__rtruediv__

      Concatenates the paths *path* and *other*.

      *path* must be a :class:`dlb.fs.Path`.
      *other* can be a :class:`dlb.fs.Path` or anything a :class:`dlb.fs.Path` can be constructed from.

      The returned path *result* is of type *C* and is constructed from ``path.components + C(other).parts``
      where *C* is the class of *path*.
      :attr:`result.is_dir <is_dir>` is ``C(other).is_dir``.

      Raises :exc:`ValueError` if *path* is not a directory path.
      Raises :exc:`ValueError` if ``C(other)`` is an absolute path.

      Examples::

         >>> dlb.fs.NoSpacePath('path/to/glory/') / 'Stanley_Kubrick'
         NoSpacePath('path/to/glory/Stanley_Kubrick')

         >>> dlb.fs.NoSpacePath('path/to/glory/') / 'Stanley Kubrick'
         Traceback (most recent call last):
         ...
         ValueError: invalid path for 'NoSpacePath': 'Stanley Kubrick' (must not contain space)

         >>> title = 'Paths to Glory'; year = 1957
         >>> dlb.fs.Path('films/') / f'{title} ({year})/' / 'video.mp4'
         Path('films/Paths to Glory (1957)/video.mp4')

.. class:: Path.Native

   A native path whose instances can be used much like instances of :class:`pathlib.Path`.
   It implements the :class:`os.PathLike` protocol.

   For each subclass *P* of :class:`dlb.fs.Path` there is a corresponding subclass ``P.Native`` that imposes the same
   restrictions on its representable paths as *P*.

   If *Q* is a subclass of *P* and *P* is a subclass of :class:`dlb.fs.Path`, then ``Q.Native`` is a subclass
   of ``P.Native``.

   Example (on a POSIX system)::

      >>> dlb.fs.NoSpacePath.Native('/tmp/x y')
      Traceback (most recent call last):
      ...
      ValueError: invalid path for 'NoSpacePath': '/tmp/x y' (must not contain space)

   In contrast to :class:`pathlib.Path`, conversion to string is done in a safe way:
   relative paths are guaranteed to start with ``'.'``.

   Example (on a POSIX system)::

       >>> str(dlb.fs.Path.Native('-rf'))
       './-rf'

   Instances of :class:`dlb.fs.Path.Native` and its subclasses should not be constructed directly but by accessing
   :attr:`dlb.fs.Path.native`.

   Example (on a POSIX system)::

      with open(dlb.fs.NoSpacePath('/tmp/x/a').native) as f:
          ... = f.read()

   .. attribute:: raw

      This path as a :class:`python:pathlib.Path`.
      Use it to access the filesystem in an object-oriented manner::

         p = dlb.fs.Path('/usr/bin/')
         ... = p.native.raw.stat()

      This attribute cannot be written.

      Constructing a :class:`python:pathlib.Path` is an expensive operation.
      For performance-critical tasks, use ``p.native`` and functions for string-like paths instead:
      e.g. ``os.path.isdir(p.native)`` instead of ``p.native.raw.is_dir()``.


.. _dlb-fs-restricting-paths:

Restricting paths
-----------------

Trying to construct a :class:`dlb.fs.Path` from an invalid value raises an :exc:`ValueError` exception.
Additional restrictions to the set of valid values can be imposed on instances of :class:`dlb.fs.Path` by subclassing.

A subclass of :class:`dlb.fs.Path` should only implement :meth:`check_restriction_to_base`.
:meth:`p.check_restriction_to_base()` should raise :exc:`ValueError` if it considers
:attr:`p.components <dlb.fs.Path.components>` or :attr:`p.is_dir <dlb.fs.Path.is_dir>` as invalid::

   class NoBullshitPath(Path):

       def check_restriction_to_base(self, components_checked: bool):
           # This is called during construction of a NoBullshitPath after all
           # attributes have been assigned and the check_restriction_to_base() of all its
           # base classes have been called successfully.
           # *components_checked* is True if this method was called before on a path p
           # whose p.components contained all members of self.components.

           if not components_checked and any(c == 'bullshit' for c in self.components):
               raise ValueError('no bullshit, please')

   NoBullshitPath('thats/bullshit/)  # raises ValueError


.. inheritance-diagram:: dlb.fs.Path dlb.fs.RelativePath dlb.fs.AbsolutePath dlb.fs.NoSpacePath dlb.fs.PosixPath dlb.fs.PortablePosixPath dlb.fs.PortableWindowsPath dlb.fs.WindowsPath dlb.fs.PortablePath

.. class:: RelativePath

   A :class:`dlb.fs.Path` that represents a relative path.

.. class:: AbsolutePath

   A :class:`dlb.fs.Path` that represents an absolute path.

.. class:: NormalizedPath

   A :class:`dlb.fs.Path` that represents a :term:`normalized path` (without  ``'..'`` components).

.. class:: NoSpacePath

   A :class:`dlb.fs.Path` whose components do not contain ``' '``.

.. class:: PosixPath

   A :class:`dlb.fs.Path` that represents a POSIX-compliant (`ISO 1003.1-2008`_) paths in its least-constricted form.

   Every non-empty string that does not contain ``'/'`` or U+0000 (NUL) is a valid component.

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

   A :class:`dlb.fs.PosixPath` that represents a POSIX-compliant (`ISO 1003.1-2008`_) path in its strictest form.
   Any path whose support is not required by POSIX or is declared as non-portable is considered invalid.

   A component cannot be longer than 14 characters, which must all be members of the *Portable Filename Character Set*.

   The length of the string representation of the path is limited to 255 characters.

   No absolute path prefix other than ``'/'`` is allowed (because implementation-defined).

.. class:: WindowsPath

   A :class:`dlb.fs.Path` that represents a Microsoft Windows-compliant file or directory path in its
   least-constricted form, which is either relative or absolute and is not a reserved non-directory path (e.g. ``NUL``).

   It cannot represent incomplete paths which are neither absolute nor relative to the current working directory
   (e.g. ``C:a\b`` and ``\\name``).
   It cannot represent NTFS stream names, Win32 file namespaces, or Win32 device namespaces.

.. class:: PortableWindowsPath

   A :class:`dlb.fs.WindowsPath` that represents a Microsoft Windows-compliant path in its strictest form.

   A component cannot end with ``' '`` or ``'.'`` (except ``'.'`` and ``'..'``) and
   cannot be longer than 255 characters.
   The path cannot not be longer than 259 characters.

.. class:: PortablePath

