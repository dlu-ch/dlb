import functools
import pathlib  # since Python 3.4

@functools.total_ordering
class Path:

    # cannot derive easily from pathlib.Path without defining non-API members
    class Native:

        def __init__(self, path):
            self._native = pathlib.Path(path)

        def __getattr__(self, item):
            return getattr(pathlib.Path, item)

        def __str__(self):
            s = str(self._native)
            if not self._native.anchor:  # with anchor: 'c:x', 'c:/x', '//unc/root/x'
                if s != '.' and self._native.parts[:1] != ('..',):
                    s = str('_.' / self._native)[1:]
            return s

    def __init__(self, path):
        if isinstance(path, Path):
            self._path = path._path
            self._is_dir = path._is_dir
        else:
            if isinstance(path, pathlib.PurePath) and not isinstance(path, pathlib.Path):
                path = str(path)
            elif path is None:
                raise ValueError('invalid path: None')
            else:
                path = str(path)
            if not path:
                raise ValueError("invalid path: ''")
            self._path = pathlib.PurePosixPath(path)  # '.' represented as empty path
            self._is_dir = path.endswith('/') or path.endswith('/.') \
                or not self._path.parts or self._path.parts[-1:] == ('..',)

        try:
            for c in reversed(self.__class__.mro()):
                if 'check_restriction_to_base' in c.__dict__:
                    c.check_restriction_to_base(self)
        except ValueError as e:
            reason = str(e)
            msg = "invalid path for {}: {}".format(repr(self.__class__.__qualname__), repr(str(self._path)))
            if reason:
                msg = '{} ({})'.format(msg, reason)
            raise ValueError(msg)

    def is_absolute(self):
        return self._path.is_absolute()

    def is_dir(self):
        return self._is_dir

    def relative_to(self, other):
        other = self.__class__(other)
        if not other.is_dir():
            raise ValueError('since {} is not a directory, a path cannot be relative to it'.format(repr(other)))
        return self.__class__(self._path.relative_to(other._path))

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

        s = str(self._path)
        if s.startswith('/') and not s.startswith('//'):
            s = s[1:]
        # accepted: c:x/y, c:/x/y, //unc/root/x/y
        return pathlib.PureWindowsPath(s)

    @property
    def native(self):
        if not issubclass(self.Native, pathlib.PosixPath):
            return self.Native(self.pure_posix)
        if issubclass(self.Native, pathlib.WindowsPathPath):
            return self.Native(self.pure_windows)
        raise TypeError("unknown 'Native' class: {}".format(repr(self.Native)))

    def __truediv__(self, other):
        if not self.is_dir():
            raise ValueError('cannot join with non-directory path {}'.format(repr(self)))
        return self.__class__(self._path / self.__class__(other)._path)

    def __rtruediv__(self, other):
        other = self.__class__(other)
        if not other.is_dir():
            raise ValueError('cannot join with non-directory path {}'.format(repr(other)))
        return self.__class__(self.__class__(other)._path / self._path)

    def __eq__(self, other):
        # on all platform, comparision is case sensitive
        other = self.__class__(other)
        return (self._path, self._is_dir) == (other._path, other._is_dir)

    def __lt__(self, other):
        other = self.__class__(other)
        return (self._path, not self._is_dir) < (other._path, not other._is_dir)

    def __hash__(self):
        return hash((self._path, self._is_dir))

    def __repr__(self):
        s = str(self._path)
        if self.is_dir() and not s.endswith('/'):
            s += '/'
        return '{}({})'.format(self.__class__.__qualname__, repr(s))  # since Python 3.3

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
    which is either relative or absolute (but not drive-relativ like ``C:x\y`) and does not contain components
    with reserved names (like ``NUL``).
    """

    def check_restriction_to_base(self):
        p = self.pure_windows
        if len(p.parts) > 1 and p.anchor and not p.root:
            raise ValueError('root is missing')
        for c in p.parts[1:]:  # except anchor
            if pathlib.PureWindowsPath(c).is_reserved():
                raise ValueError('component {} is reserved'.format(repr(c)))


class PortableWindowsPath(Path):

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
