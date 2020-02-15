# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Classes to represent and access filesystem objects in a safe and platform-independent manner."""

__all__ = (
    'Path', 'RelativePath', 'AbsolutePath', 'NormalizedPath', 'NoSpacePath',
    'PosixPath', 'PortablePosixPath',
    'PortableWindowsPath', 'WindowsPath',
    'PortablePath'
)

import sys
import re
import os
import functools
import pathlib  # since Python 3.4
import typing
assert sys.version_info >= (3, 7)


# cannot derive easily from pathlib.Path without defining non-API members
class _Native:

    def __init__(self, path):
        self._raw = pathlib.Path(path)

    @property
    def raw(self) -> pathlib.Path:
        return self._raw

    def __fspath__(self) -> str:  # make this class a safer os.PathLike
        return str(self)

    def __str__(self) -> str:
        r = self._raw
        s = str(r)
        if not r.anchor:  # with anchor: 'c:x', 'c:/x', '//unc/root/x'
            if s != '.' and r.parts[:1] != ('..',):
                # noinspection PyUnresolvedReferences
                s = str('_.' / r)[1:]
        return s

    def __repr__(self) -> str:
        return f'Path.Native({str(self)!r})'

    def __getattr__(self, item):
        return getattr(self._raw, item)


# http://stackoverflow.com/questions/13762231/python-metaclass-arguments
# noinspection PyMethodParameters,PyProtectedMember,PyUnresolvedReferences
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


# noinspection PyMethodParameters,PyProtectedMember,PyUnresolvedReferences
class _NativeMeta(_Meta):
    def __call__(mcl, value):
        obj = _Native(value)
        mcl._cls(obj._raw)
        return obj

    def __instancecheck__(mcl, instance) -> bool:
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
    def __init__(self, path, is_dir: typing.Optional[bool] = None):
        if path is None:
            raise ValueError('invalid path: None')

        if isinstance(path, _Native):
            path = path.raw

        if isinstance(path, Path):
            # copy
            self._path = path._path
            self._is_dir = path._is_dir
        else:
            # convert
            if isinstance(path, pathlib.PurePosixPath):  # this should be very efficient
                self._path = path
                self._is_dir = False
            elif isinstance(path, str):
                if not path:
                    raise ValueError("invalid path: ''")
                self._path = pathlib.PurePosixPath(path)  # '' -> pathlib.PurePosixPath('.')
                self._is_dir = path.endswith('/') or path.endswith('/.')
            elif isinstance(path, pathlib.PureWindowsPath):
                self._check_windows_path_anchor(path)
                p = str(path).replace('\\', '/')
                if path.anchor and path.anchor[0] not in '/\\':
                    p = '/' + p
                self._path = pathlib.PurePosixPath(p)  # '' -> pathlib.PurePosixPath('.')
                self._is_dir = p.endswith('/')
            elif isinstance(path, pathlib.PurePath):
                raise TypeError("unknown subclass of 'pathlib.PurePath'")
            else:
                raise TypeError(f'argument should be a path or str object, not {path.__class__!r}')  # like pathlib

            self._is_dir = self._is_dir or not self._path.parts or self._path.parts[-1:] == ('..',)

        if is_dir is not None:
            is_dir = bool(is_dir)
            if not is_dir and (not self._path.parts or self._path.parts[-1:] == ('..',)):
                raise ValueError(f'cannot be the path of a non-directory: {str(self._path)!r}')
            self._is_dir = is_dir

        try:
            for c in reversed(self.__class__.mro()):
                if 'check_restriction_to_base' in c.__dict__:
                    # noinspection PyUnresolvedReferences
                    c.check_restriction_to_base(self)
        except ValueError as e:
            reason = str(e)
            msg = f'invalid path for {self.__class__.__qualname__!r}: {str(self._path)!r}'
            if reason:
                msg = f'{msg} ({reason})'
            raise ValueError(msg)

    @classmethod
    def _check_windows_path_anchor(cls, path):
        if path.anchor:
            if not path.root:
                raise ValueError('neither absolute nor relative: root is missing')
            if not path.drive:
                raise ValueError('neither absolute nor relative: drive is missing')

    def is_dir(self) -> bool:
        return self._is_dir

    def is_absolute(self) -> bool:
        return self._path.is_absolute()

    def is_normalized(self) -> bool:
        return '..' not in self.parts

    def relative_to(self, other):
        other = self.__class__(other)
        if not other.is_dir():
            raise ValueError(f'since {other!r} is not a directory, a path cannot be relative to it')
        return self.__class__(self._path.relative_to(other._path), is_dir=self._is_dir)

    def iterdir(self, name_filter='', recurse_name_filter=None, follow_symlinks: bool = True, cls=None):
        if not self.is_dir():
            raise ValueError(f'cannot list non-directory path: {self.as_string()!r}')

        def make_name_filter(f):
            if f is None:
                return lambda s: False
            if callable(f):
                return f
            if isinstance(f, typing.Pattern):
                return lambda s: f.fullmatch(s)  # since Python 3.4
            if isinstance(f, str):
                if f:
                    r = re.compile(f)
                    return lambda s: r.fullmatch(s)  # since Python 3.4
                else:
                    return lambda s: True
            raise TypeError(f'invalid name filter: {f!r}')

        name_filter = make_name_filter(name_filter)
        recurse_name_filter = make_name_filter(recurse_name_filter)

        if cls is None:
            cls = self.__class__
        if not (isinstance(cls, type) and issubclass(cls, Path)):
            raise TypeError("'cls' must be None or a subclass of 'dlb.fs.Path'")

        dir_paths_to_recurse = [Path(self)]
        while dir_paths_to_recurse:

            dir_path = dir_paths_to_recurse.pop(0)
            with os.scandir(dir_path.native.raw) as it:  # since Python 3.6

                paths = []
                for de in it:
                    n = de.name
                    d = de.is_dir(follow_symlinks=follow_symlinks)
                    does_name_match = name_filter(n)
                    do_recurse = d and recurse_name_filter(n)

                    p = None
                    if does_name_match or do_recurse:
                        p = dir_path / Path(n, d)

                    if does_name_match:
                        paths.append(p)
                    if do_recurse:
                        dir_paths_to_recurse.append(p)

                paths.sort()
                for p in paths:
                    yield cls(p)

            dir_paths_to_recurse.sort()

    def iterdir_r(self, name_filter='', recurse_name_filter=None, follow_symlinks: bool = True, cls=None):
        for p in self.iterdir(name_filter, recurse_name_filter, follow_symlinks, cls):
            yield p.relative_to(self)

    def list(self, name_filter='', recurse_name_filter=None, follow_symlinks: bool = True, cls=None):
        return sorted(self.iterdir(name_filter, recurse_name_filter, follow_symlinks, cls))

    def list_r(self, name_filter='', recurse_name_filter=None, follow_symlinks: bool = True, cls=None):
        return sorted(self.iterdir_r(name_filter, recurse_name_filter, follow_symlinks, cls))

    @property
    def _cparts(self):
        return self.parts if self.is_absolute() else ('',) + self.parts

    @property
    def parts(self) -> typing.Tuple[str, ...]:
        return self._path.parts

    @property
    def pure_posix(self) -> pathlib.PurePosixPath:
        return self._path

    @property
    def pure_windows(self) -> pathlib.PureWindowsPath:
        s = self.as_string()
        if s.startswith('/') and not s.startswith('//'):
            s = s[1:]

        # accepted: 'c:x', 'c:/x', '//unc/root/x/y'
        p = pathlib.PureWindowsPath(s)
        self._check_windows_path_anchor(p)

        if p.is_reserved():
            # not actually reserved for directory path, but this information is last after conversion
            raise ValueError(f'file path is reserved: {str(p)!r}')

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

    def as_string(self) -> str:
        s = str(self._path)
        if self.is_dir() and not s.endswith('/'):
            s += '/'
        return s

    def __truediv__(self, other):
        if not self.is_dir():
            raise ValueError(f'cannot append to non-directory path: {self!r}')
        other = self.__class__(other)
        if other.is_absolute():
            raise ValueError(f'cannot append absolute path: {other!r}')
        return self.__class__(self._path / other._path, is_dir=other._is_dir)

    def __rtruediv__(self, other):
        return self.__class__(other) / self

    def __eq__(self, other) -> bool:
        # on all platform, comparison is case sensitive
        other = self.__class__(other)
        return (self._cparts, self._is_dir) == (other._cparts, other._is_dir)

    def __lt__(self, other) -> bool:
        other = self.__class__(other)
        return (self._cparts, self._is_dir) < (other._cparts, other._is_dir)

    def __hash__(self) -> int:
        return hash((self._path, self._is_dir))

    def __repr__(self) -> str:
        return f'{self.__class__.__qualname__}({self.as_string()!r})'

    def __str__(self):
        # make sure this object is not converted to a string where a native path is expected
        # (not to be implemented by subclasses, hence not NotImplementedError)
        raise AttributeError("use 'repr()' or 'native' instead")

    def __getitem__(self, item):
        if not isinstance(item, slice):
            raise TypeError("slice of component indices expected (use 'parts' for single components)")
        n = len(self.parts)
        start, stop, step = item.indices(n)
        assert 0 <= start <= n
        assert -1 <= stop <= n
        if start == 0 and stop >= n and step == 1:
            return self
        else:
            c = self.parts[start:stop:step]
            if self.is_absolute() and not c:
                raise ValueError("slice of absolute path must not be empty")
            p = pathlib.PurePosixPath(*c)
            d = stop < n or self._is_dir
            return self.__class__(p, d)


class RelativePath(Path):
    def check_restriction_to_base(self):
        if self.is_absolute():
            raise ValueError('must be relative')


class AbsolutePath(Path):
    def check_restriction_to_base(self):
        if not self.is_absolute():
            raise ValueError('must be absolute')


class NormalizedPath(Path):
    def check_restriction_to_base(self):
        if not self.is_normalized():
            raise ValueError('must be normalized')


class NoSpacePath(Path):
    def check_restriction_to_base(self):
        if ' ' in str(self._path):
            raise ValueError('must not contain space')


class PosixPath(Path):
    def check_restriction_to_base(self):
        if '\0' in str(self._path):
            raise ValueError('must not contain NUL')


class PortablePosixPath(PosixPath):
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

        for c in self.parts:
            if c != '/':
                if len(c) > self.MAX_COMPONENT_LENGTH:
                    raise ValueError(f'component must not contain more than {self.MAX_COMPONENT_LENGTH} characters')

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
            raise ValueError(f'must not contain more than {self.MAX_PATH_LENGTH} characters')


class WindowsPath(Path):
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
    RESERVED_CHARACTERS = frozenset('\\"|?*<>:')  # besides: '/'

    def check_restriction_to_base(self):
        for c in self._path.parts:
            invalid_characters = set(c) & self.RESERVED_CHARACTERS
            if invalid_characters:
                raise ValueError("must not contain reserved characters: {0}".format(
                    ','.join(repr(c) for c in sorted(invalid_characters))))

        s = self.as_string()

        # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
        min_codepoint = ord(min(s))
        if min_codepoint < 0x20:
            raise ValueError(f'must not contain characters with codepoint lower than U+0020: U+{min_codepoint:04X}')

        max_codepoint = ord(max(s))
        if max_codepoint > 0xFFFF:
            raise ValueError(f'must not contain characters with codepoint higher than U+FFFF: U+{max_codepoint:04X}')

        p = pathlib.PureWindowsPath(self._path)
        self._check_windows_path_anchor(p)

        if not self.is_dir() and p.is_reserved():
            raise ValueError('path is reserved')


class PortableWindowsPath(WindowsPath):
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx#maxpath
    MAX_COMPONENT_LENGTH = 255  # lpMaximumComponentLength
    MAX_PATH_LENGTH = 259  # MAX_PATH - 1

    def check_restriction_to_base(self):
        p = self.pure_windows
        for c in p.parts[1:]:  # except anchor
            if len(c) > self.MAX_COMPONENT_LENGTH:
                raise ValueError(f'component must not contain more than {self.MAX_COMPONENT_LENGTH} characters')
            if c != '..' and c[-1] in ' .':
                # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
                raise ValueError("component must not end with ' ' or '.'")

        n = len(str(p))
        if self.is_dir():
            n += 1
        if n > self.MAX_PATH_LENGTH:
            raise ValueError(f'must not contain more than {self.MAX_PATH_LENGTH} characters')


class PortablePath(PortablePosixPath, PortableWindowsPath, RelativePath):
    pass
