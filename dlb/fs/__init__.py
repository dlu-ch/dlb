import functools
import copy
import pathlib  # since Python 3.4

__all__ = [
    'Path', 'RelativePath', 'AbsolutePath', 'NoSpacePath',
    'PosixPath', 'PortablePosixPath',
    'PortableWindowsPath', 'WindowsPath',
    'PortablePath'
]


# cannot derive easily from pathlib.Path without defining non-API members
class _Native:
    def __init__(self, path):
        self._raw = pathlib.Path(path)

    @property
    def raw(self):
        return self._raw

    def __str__(self):
        r = self._raw
        s = str(r)
        if not r.anchor:  # with anchor: 'c:x', 'c:/x', '//unc/root/x'
            if s != '.' and r.parts[:1] != ('..',):
                s = str('_.' / r)[1:]
        return s

    def __repr__(self):
        return 'Path.Native({})'.format(repr(str(self)))

    def __getattr__(self, item):
        return getattr(pathlib.Path, item)


# http://stackoverflow.com/questions/13762231/python-metaclass-arguments
class _Meta(type):
    def __subclasscheck__(mcl, subclass):
        # Class hierarchy:
        #
        #   B > A > Path   ==>   A.Native > B.Native > _Native
        #
        # Note: the class hierarchy induced by issubclass() reflects only the (static) hierarchy
        # provided by Path classes. On the other hand, the object hierarchy induced by isinstance()
        # is based on (dynamic) properties of the Path's components.
        common_bases = set(mcl.__class__.__bases__) & set(subclass.__class__.__bases__)
        return common_bases and issubclass(subclass._cls, mcl._cls)


class _NativeMeta(_Meta):
    def __call__(mcl, value):
        obj = _Native(value)
        mcl._cls(obj._raw)
        return obj

    def __instancecheck__(mcl, instance):
        if not isinstance(instance, _Native):
            return False
        try:
            mcl._cls(instance._raw)
        except ValueError:
            return False
        return True


class _PathMeta(type):
    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)
        meta = type(cls.__name__ + '.<NativeMeta>', (_NativeMeta,), {'_cls': cls})
        cls.Native = meta(cls.__name__ + '.Native', (_Native,), {})


@functools.total_ordering
class Path(metaclass=_PathMeta):
    def __init__(self, path, is_dir=None):
        if path is None:
            raise ValueError('invalid path: None')

        if isinstance(path, Path):
            self._path = path._path
            self._is_dir = path._is_dir
        else:
            if isinstance(path, str):
                p = path
            elif isinstance(path, pathlib.PurePath):
                p = str(path)
                if isinstance(path, pathlib.PurePosixPath):
                    pass
                elif isinstance(path, pathlib.PureWindowsPath):
                    if path.anchor:
                        if not path.root:
                            raise ValueError('neither absolute nor relative: root is missing')
                        if not path.drive:
                            raise ValueError('neither absolute nor relative: drive is missing')
                    p = p.replace('\\', '/')
                    if path.anchor and path.anchor[0] not in '/\\':
                        p = '/' + p
                else:
                    raise TypeError("unknown subclass of 'pathlib.PurePath'")
            else:
                # like pathlib
                raise TypeError(
                    "argument should be a path or str object, not {}".format(repr(path.__class__)))

            if not p:
                raise ValueError("invalid path: ''")
            self._path = pathlib.PurePosixPath(p)  # '.' represented as empty path
            self._is_dir = p.endswith('/') or p.endswith('/.') \
                           or not self._path.parts or self._path.parts[-1:] == ('..',)

        if is_dir is not None:
            is_dir = bool(is_dir)
            if not is_dir and (not self._path.parts or self._path.parts[-1:] == ('..',)):
                raise ValueError(
                    'cannot be the path of a non-directory: {}'.format(repr(str(self._path))))
            self._is_dir = is_dir

        try:
            for c in reversed(self.__class__.mro()):
                if 'check_restriction_to_base' in c.__dict__:
                    c.check_restriction_to_base(self)
        except ValueError as e:
            reason = str(e)
            msg = "invalid path for {}: {}".format(
                repr(self.__class__.__qualname__), repr(str(self._path)))
            if reason:
                msg = '{} ({})'.format(msg, reason)
            raise ValueError(msg)

    def is_dir(self):
        return self._is_dir

    def is_absolute(self):
        return self._path.is_absolute()

    def relative_to(self, other):
        other = self.__class__(other)
        if not other.is_dir():
            raise ValueError(
                'since {} is not a directory, a path cannot be relative to it'.format(repr(other)))
        return self.__class__(self._path.relative_to(other._path), is_dir=self._is_dir)

    @property
    def parts(self):
        """
        A tuple giving access to the path’s various components::

            >>> p = Path('/usr/bin/python3')
            >>> p.parts
            ('/', 'usr', 'bin', 'python3')

        :rtype: tuple(str)
        """
        return self._path.parts

    @property
    def pure_posix(self):
        """
        This path as a ::class::``PurePosixPath``::

            >>> p = Path('/usr/bin/')
            >>> p.pure_posix
            PurePosixPath('/usr/bin')

        :rtype: pathlib.PurePosixPath
        """
        return self._path

    @property
    def pure_windows(self):
        """
        This path as a ::class::``PureWindowsPath``::

            >>> p = Path('/C:/Program Files/')
            >>> p.pure_windows
            PureWindowsPath('C:/Program Files')

        :rtype: pathlib.PureWindowsPath
        """

        s = self._str()
        if s.startswith('/') and not s.startswith('//'):
            s = s[1:]

        # accepted: 'c:x', 'c:/x', '//unc/root/x/y'
        p = pathlib.PureWindowsPath(s)
        if p.anchor:
            if not p.root:
                raise ValueError('neither absolute nor relative: root is missing')
            if not p.drive:
                raise ValueError('neither absolute nor relative: drive is missing')

        return p

    if isinstance(pathlib.Path(), pathlib.PosixPath):

        @property
        def native(self):
            return _Native(self.pure_posix)

    elif isinstance(pathlib.Path(), pathlib.WindowsPath):

        @property
        def native(self):
            return _Native(self.pure_windows)

    else:
        raise TypeError("unknown 'Native' class")

    def _str(self):
        s = str(self._path)
        if self.is_dir() and not s.endswith('/'):
            s += '/'
        return s

    def __truediv__(self, other):
        if not self.is_dir():
            raise ValueError('cannot join with non-directory path: {}'.format(repr(self)))
        other = self.__class__(other)
        if other.is_absolute():
            raise ValueError('cannot join with absolute path: {}'.format(repr(other)))
        return self.__class__(self._path / other._path, is_dir=other._is_dir)

    def __rtruediv__(self, other):
        return self.__class__(other) / self

    def __eq__(self, other):
        # on all platform, comparison is case sensitive
        other = self.__class__(other)
        return (self._path, self._is_dir) == (other._path, other._is_dir)

    def __lt__(self, other):
        other = self.__class__(other)
        return (self._path, not self._is_dir) < (other._path, not other._is_dir)

    def __hash__(self):
        return hash((self._path, self._is_dir))

    def __repr__(self):
        return '{}({})'.format(self.__class__.__qualname__, repr(self._str()))  # since Python 3.3

    def __str__(self):
        # make sure this object is not converted to a string where a native path is expected
        raise NotImplementedError("use 'repr()' or 'native' instead")


class RelativePath(Path):
    def check_restriction_to_base(self):
        if self.is_absolute():
            raise ValueError('must be relative')


class AbsolutePath(Path):
    def check_restriction_to_base(self):
        if not self.is_absolute():
            raise ValueError('must be absolute')


class NoSpacePath(Path):
    def check_restriction_to_base(self):
        if ' ' in str(self._path):
            raise ValueError('must not contain space')


class PosixPath(Path):
    """
    A :class:`Path` which represents a POSIX-compliant (`ISO 1003.1-2008`_) paths in its least-constricted form.

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
    """
    pass


class PortablePosixPath(PosixPath):
    """
    A :class:`Path` which represents a POSIX-compliant (`ISO 1003.1-2008`_) path in its strictest form.
    Any path whose support is not required by POSIX or is declared as non-portable is considered invalid.

    A component cannot be longer than 14 characters, which must all be members of the
    *Portable Filename Character Set*.

    The length of the string representation of the path is limited to 255 characters.

    No absolute path prefix other than ``'/'`` is allowed (because implementation-defined).
    """

    MAX_COMPONENT_LENGTH = 14  # {_POSIX_NAME_MAX}
    MAX_PATH_LENGTH = 255  # {_POSIX_PATH_MAX} - 1
    CHARACTERS = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-')

    def check_restriction_to_base(self):

        # IEEE Std 1003.1-2008, 4.13 Pathname Resolution:
        #
        #   If a pathname begins with two successive <slash> characters, the first component following the
        #   leading <slash> characters may be interpreted in an implementation-defined manner, although more
        #   than two leading <slash> characters shall be treated as a single <slash> character.

        if self._path.anchor == '//':
            raise ValueError("non-standardized component starting with '//' not allowed")

        for c in self._path.parts:
            if c != '/':
                if len(c) > self.MAX_COMPONENT_LENGTH:
                    raise ValueError('component must not contain more than {} characters'.format(
                        self.MAX_COMPONENT_LENGTH))

                # IEEE Std 1003.1-2008, section 4.7 Filename Portability
                if c.startswith('-'):
                    raise ValueError("component must not start with '-'")

                # IEEE Std 1003.1-2008, section 3.278 Portable Filename Character Set
                invalid_characters = set(c) - self.CHARACTERS
                if invalid_characters:
                    raise ValueError("must not contain these characters: {0}".format(
                        ','.join(repr(c) for c in sorted(invalid_characters))))

        n = len(str(self._path))
        if self.is_dir():
            n += 1
        if n > self.MAX_PATH_LENGTH:
            raise ValueError('must not contain more than {} characters'.format(self.MAX_PATH_LENGTH))


class WindowsPath(Path):
    """
    A :class:`Path` which represents a Microsoft Windows-compliant path in its least-constricted form,
    which is either relative or absolute and does not contain components with reserved names (like ``NUL``).

    It cannot represent incomplete paths which are neither absolute nor relative to the current working
    directory (e.g. ``C:a\b`` and ``\\name``).
    """

    def check_restriction_to_base(self):
        p = self.pure_windows
        if len(p.parts) > 1 and p.anchor and not p.root:
            raise ValueError('root is missing')
        for c in p.parts[1:]:  # except anchor
            if pathlib.PureWindowsPath(c).is_reserved():
                raise ValueError('component {} is reserved'.format(repr(c)))


class PortableWindowsPath(WindowsPath):
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx#maxpath
    MAX_COMPONENT_LENGTH = 255  # lpMaximumComponentLength
    MAX_PATH_LENGTH = 259  # MAX_PATH - 1

    def check_restriction_to_base(self):
        p = self.pure_windows
        for c in p.parts[1:]:  # except anchor
            if len(c) > self.MAX_COMPONENT_LENGTH:
                raise ValueError('component must not contain more than {} characters'.format(
                    self.MAX_COMPONENT_LENGTH))

        n = len(str(p))
        if self.is_dir():
            n += 1
        if n > self.MAX_PATH_LENGTH:
            raise ValueError('must not contain more than {} characters'.format(self.MAX_PATH_LENGTH))


class PortablePath(PortablePosixPath, PortableWindowsPath, RelativePath): pass
