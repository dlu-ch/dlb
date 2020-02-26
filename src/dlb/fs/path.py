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
import collections.abc
import functools
import pathlib  # since Python 3.4
from typing import Pattern, Optional, Tuple
assert sys.version_info >= (3, 7)


class _NativeComponents:  # TODO find better name

    def __init__(self, components: Tuple[str, ...], sep: str):
        # - *components* has at least one element
        # - the first element is '' if and only if it represents a relative path
        # - if the first element is not '' it represents an absolute path (e.g. 'C:\\')
        # - no element except possibly the first one contains *sep*
        self._components = components
        self._sep = sep

    @property
    def components(self):
        return self._components

    @property
    def sep(self):
        return self._sep

    def __str__(self):
        # must be fast and safe
        # each relative path starts with '.' or '..'

        c = self._components
        if len(c) <= 1:
            return c[0] if c[0] else '.'

        s = c[0]
        if s:
            # absolute path
            if s[-1] != self._sep:
                s += self._sep  
        else:
            # relative path
            if len(c) > 1 and c[1] != '..': 
                s = '.' + self._sep

        return s + self._sep.join(c[1:])


def _native_components_for_posix(components: Tuple[str, ...]) -> Tuple[str, ...]:
    # first element of components is '', '/', or '//'
    return _NativeComponents(components, '/')


def _native_components_for_windows(components: Tuple[str, ...]) -> Tuple[str, ...]:
    # first element of components is '', '/', or '//'
    if any('\\' in c for c in components):
        raise ValueError("must not contain reserved characters: '\\\\'")

    # ('/', 'c:', 'temp') -> ('c:\\', 'temp')
    # ('//', 'u', 'r')    -> ('\\u\\r',)
    first_component = components[0]
    if first_component == '/':
        if len(components) <= 1:
            raise ValueError('neither absolute nor relative: root is missing')
        anchor = components[1]
        if not (anchor[-1:] == ':' and anchor[:-1]):
            raise ValueError('neither absolute nor relative: drive is missing')
        components = components[1:]
        components = (anchor + '\\',) + components[1:]
        first_component = anchor[:-1]
    elif first_component == '//':
        if len(components) <= 2:
            raise ValueError('neither absolute nor relative: drive is missing')
        first_component = '\\\\' + components[1] + '\\' + components[2]
        components = (first_component,) + components[3:]

    if ':' in first_component or any(':' in c for c in components[1:]):
        raise ValueError("must not contain reserved characters: ':'")

    return _NativeComponents(components, '\\')


if isinstance(pathlib.Path(), pathlib.PosixPath):
    _native_components = _native_components_for_posix
elif isinstance(pathlib.Path(), pathlib.WindowsPath):
    _native_components = _native_components_for_windows
else:
    raise TypeError("unknown 'Native' class")


# cannot derive easily from pathlib.Path without defining non-API members
class _Native:

    def __init__(self, path):
        if isinstance(path, _NativeComponents):
            self._native_components = path
            self._raw = None  # construction only when needed
        else:
            self._raw = pathlib.Path(path)  # slow

            parts = self._raw.parts
            if not self._raw.anchor or not parts:
                components = ('',) + parts  # relative
            elif not self._raw.is_absolute():
                raise ValueError("'path' is neither relative nor absolute")
            else:
                components = parts  # absolute

            self._native_components = _NativeComponents(components, os.path.sep)

        # note: metaclass _NativeMeta checks self.components after construction

    @property
    def components(self) -> _NativeComponents:
        return self._native_components.components

    @property
    def raw(self) -> pathlib.Path:
        if self._raw is None:
            self._raw = pathlib.Path(str(self._native_components))
        return self._raw

    def __fspath__(self) -> str:  # make this class a safer os.PathLike
        return str(self)

    def __str__(self) -> str:
        s = str(self._native_components)
        return s

    def __repr__(self) -> str:
        return f'Path.Native({str(self)!r})'

    def __getattr__(self, item):
        return getattr(self.raw, item)


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
        mcl._cls(obj.components)  # check restrictions
        return obj

    def __instancecheck__(mcl, instance) -> bool:
        if not isinstance(instance, _Native):
            return False
        try:
            mcl._cls(instance.components)
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
    def __init__(self, path, *, is_dir: Optional[bool] = None):
        if path is None:
            raise ValueError('invalid path: None')

        check = True

        if isinstance(path, Path):

            # P(P()) must be very fast for every subclass of Path
            self._components = path._components
            self._is_dir = path._is_dir
            check = self.__class__  is not path.__class__

        elif isinstance(path, str):

            if not path:
                raise ValueError("invalid path: ''")

            anchor = ''
            if path[:3] == '///':
                anchor = '/'
            elif path[:2] == '//':
                anchor = '//'
            elif path[:1] == '/':
                anchor = '/'
            nonanchor_components = tuple(c for c in path.strip('/').split('/') if c and c != '.')

            self._components = (anchor,) + nonanchor_components
            self._is_dir = path.endswith('/') or path.endswith('/.')

        elif isinstance(path, collections.abc.Sequence):

            components = tuple(str(c) for c in path)
            if not components or components[0][:1] != '/':
                components = ('',) + components
            if components[0] not in ('', '/', '//'):
                raise ValueError("if 'path' is a parts tuple, its first element must be one of '', '/', '//'")
            nonroot_components = tuple(c for c in components[1:] if c and c != '.')
            if any('/' in c for c in nonroot_components):
                raise ValueError("if 'path' is a parts tuple, none except its first element must contain '/'")
            self._components = (components[0],) + nonroot_components
            self._is_dir = False

        else:

            # convert
            if isinstance(path, _Native):
                path = path.raw

            if not isinstance(path, pathlib.PurePath):
                raise TypeError("'path' must be a str, dlb.fs.Path or pathlib.PurePath object or a sequence")

            anchor = path.anchor

            if isinstance(path, pathlib.PurePosixPath):  # this should be very efficient
                self._components = (anchor,) + (path.parts[1:] if anchor else path.parts)
                self._is_dir = False
            elif isinstance(path, pathlib.PureWindowsPath):
                parts = path.parts
                if anchor:
                    anchor = anchor.replace('\\', '/').rstrip('/')
                    if not path.root:
                        raise ValueError('neither absolute nor relative: root is missing')
                    if not path.drive or not anchor:
                        raise ValueError('neither absolute nor relative: drive is missing')
                    nanchor = anchor.lstrip('/')
                    nanchor = '//' if len(anchor) - len(nanchor) > 1 else '/'
                    self._components = (nanchor,) + tuple(c for c in anchor.split('/') if c and c != '.') + parts[1:]
                    self._is_dir = not parts[1:]
                else:
                    self._components = ('',) + path.parts
                    self._is_dir = False
            else:
                raise TypeError("unknown subclass of 'pathlib.PurePath'")

        if is_dir is not None:
            is_dir = bool(is_dir)
            if not is_dir and (self._components == ('',) or self._components[-1:] == ('..',)):
                raise ValueError(f'cannot be the path of a non-directory: {self._as_string()!r}')
            if self._is_dir != is_dir:
                check = True
            self._is_dir = is_dir

        if check:
            if is_dir is None:
                self._sanitize_is_dir()
            self._check_constrains()

    def _cast(self, other):
        if other.__class__ is self.__class__:
            return other
        return self.__class__(other)

    def _sanitize_is_dir(self):
        self._is_dir = self._is_dir or len(self._components) <= 1 or self._components[-1:] == ('..',)

    def _check_constrains(self):
        try:
            for c in reversed(self.__class__.mro()):
                if 'check_restriction_to_base' in c.__dict__:
                    # noinspection PyUnresolvedReferences
                    c.check_restriction_to_base(self)
        except ValueError as e:
            reason = str(e)
            msg = f'invalid path for {self.__class__.__qualname__!r}: {str(self.as_string())!r}'
            if reason:
                msg = f'{msg} ({reason})'
            raise ValueError(msg) from None

    def _with_components(self, components: Tuple[str, ...], *, is_dir: Optional[bool] = None):
        p = self.__class__(self)  # fastest way of construction
        p._components = components
        if is_dir is not None:
            p._is_dir = bool(is_dir)
        p._sanitize_is_dir()
        p._check_constrains()
        return p

    def is_dir(self) -> bool:
        return self._is_dir

    def is_absolute(self) -> bool:
        return bool(self._components[0])

    def is_normalized(self) -> bool:
        return '..' not in self._components

    def relative_to(self, other):
        other = self._cast(other)
        if not other.is_dir():
            raise ValueError(f'since {other!r} is not a directory, a path cannot be relative to it')
        n = len(other._components)
        if len(self._components) < n or self._components[:n] != other._components:
            raise ValueError(f"{self.as_string()!r} does not start with {other.as_string()!r}")
        return self._with_components(('',) + self._components[n:])  # TODO avoid unnecessary checking of constraints

    def iterdir(self, name_filter='', recurse_name_filter=None, follow_symlinks: bool = True, cls=None):
        if not self.is_dir():
            raise ValueError(f'cannot list non-directory path: {self.as_string()!r}')

        def make_name_filter(f):
            if f is None:
                return lambda s: False
            if callable(f):
                return f
            if isinstance(f, Pattern):
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
                        p = dir_path / Path(n, is_dir=d)

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
    def components(self) -> Tuple[str, ...]:
        # first element is '/' or '//' if absolute and '' otherwise
        return self._components

    @property
    def parts(self) -> Tuple[str, ...]:
        # first element: '/' or '//' if absolute, does not start with '/' otherwise
        c = self._components
        if not c[0]:
            return c[1:]  # relative path
        return c

    @property
    def pure_posix(self) -> pathlib.PurePosixPath:
        return pathlib.PurePosixPath(self._as_string())

    @property
    def pure_windows(self) -> pathlib.PureWindowsPath:
        # construction from one string is much faster than several components (its also safer)
        p = pathlib.PureWindowsPath(str(_native_components_for_windows(self.components)))
        if p.is_reserved():
            # not actually reserved for directory path, but information whether directory is lost after conversion
            raise ValueError(f'path is reserved')
        return p

    @property
    def native(self):
        # must be fast
        return _Native(_native_components(self.components))  # does _not_ check restrictions again

    def _as_string(self) -> str:
        c = self._components
        if not c[0]:
            c = c[1:]  # relative
        elif len(c) > 1:
            c = (c[0] + c[1],) + c[2:]
        return '/'.join(c) if c else '.'

    def as_string(self) -> str:
        s = self._as_string()
        if not self.is_dir() or s[-1] == '/':
            return s
        return s + '/'

    def __truediv__(self, other):
        if not self.is_dir():
            raise ValueError(f'cannot append to non-directory path: {self!r}')
        other = self._cast(other)
        o = other._components
        if o[0]:
            raise ValueError(f'cannot append absolute path: {other!r}')
        if len(o) <= 1:
            return self
        # TODO avoid unnecessary checking of constraints
        return self._with_components(self._components + o[1:], is_dir=other._is_dir)

    def __rtruediv__(self, other):
        return self._cast(other) / self

    def __eq__(self, other) -> bool:
        # on all platform, comparison is case sensitive
        other = self._cast(other)
        return (self._components, self._is_dir) == (other._components, other._is_dir)

    def __lt__(self, other) -> bool:
        other = self._cast(other)
        return (self._components, self._is_dir) < (other._components, other._is_dir)

    def __hash__(self) -> int:
        return hash((self._components, self._is_dir))

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
        if step < 0:
            raise ValueError('slice step must be positive')

        if start == 0 and stop >= n and step == 1:
            return self

        parts = self.parts[start:stop:step]
        if start == 0 and self.is_absolute() and not parts:
            raise ValueError("slice of absolute path starting at 0 must not be empty")
        if not parts:
            components = ('',)
        elif parts[0][:1] == '/':
            components = parts
        else:
            components = ('',) + parts
        return self._with_components(components, is_dir=stop < n or self._is_dir)


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
        if any(' ' in c for c in self.parts):
            raise ValueError('must not contain space')


class PosixPath(Path):
    def check_restriction_to_base(self):
        if any('\0' in c for c in self.parts):
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

        components = self.components
        if components[0] == '//':
            raise ValueError("non-standardized component starting with '//' not allowed")

        for c in components[1:]:
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

        n = sum(len(c) for c in components) + max(0, len(components) - 2)
        if self.is_dir() and (len(components) > 1 or components[0]):
            n += 1
        if n > self.MAX_PATH_LENGTH:
            raise ValueError(f'must not contain more than {self.MAX_PATH_LENGTH} characters')


class WindowsPath(Path):
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
    RESERVED_CHARACTERS = frozenset('\\"|?*<>:')  # besides: '/'

    def check_restriction_to_base(self):
        # TODO remove construction of PureWindowsPath
        p = pathlib.PureWindowsPath(str(_native_components_for_windows(self.components)))
        if p.is_reserved():
            # not actually reserved for directory path, but information whether directory is lost after conversion
            raise ValueError(f'path is reserved')

        # without already checked in _native_components_for_windows()
        reserved = self.RESERVED_CHARACTERS - frozenset('\\:')

        for c in p.parts:
            invalid_characters = set(c) & reserved
            if invalid_characters:
                raise ValueError("must not contain reserved characters: {0}".format(
                    ','.join(repr(c) for c in sorted(invalid_characters))))

            # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
            min_codepoint = ord(min(c))
            if min_codepoint < 0x20:
                raise ValueError(f'must not contain characters with codepoint lower than U+0020: U+{min_codepoint:04X}')

            max_codepoint = ord(max(c))
            if max_codepoint > 0xFFFF:
                raise ValueError(f'must not contain characters with codepoint higher than U+FFFF: U+{max_codepoint:04X}')


class PortableWindowsPath(WindowsPath):
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx#maxpath
    MAX_COMPONENT_LENGTH = 255  # lpMaximumComponentLength
    MAX_PATH_LENGTH = 259  # MAX_PATH - 1

    def check_restriction_to_base(self):
        p = self.pure_windows  # TODO avoid

        components = self.components
        for c in components[1:]:
            if len(c) > self.MAX_COMPONENT_LENGTH:
                raise ValueError(f'component must not contain more than {self.MAX_COMPONENT_LENGTH} characters')
            if c != '..' and c[-1] in ' .':
                # http://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
                raise ValueError("component must not end with ' ' or '.'")

        n = sum(len(c) for c in components) + max(0, len(components) - 2)
        if self.is_dir() and (len(components) > 1 or components[0]):
            n += 1

        if n > self.MAX_PATH_LENGTH:
            raise ValueError(f'must not contain more than {self.MAX_PATH_LENGTH} characters')


class PortablePath(PortablePosixPath, PortableWindowsPath, RelativePath):
    pass
