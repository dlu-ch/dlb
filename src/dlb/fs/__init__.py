# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Classes to represent and access filesystem objects in a safe and platform-independent manner."""

__all__ = [
    'PathLike',
    'Path', 'RelativePath', 'AbsolutePath', 'NormalizedPath', 'NoSpacePath',
    'PosixPath', 'PortablePosixPath',
    'PortableWindowsPath', 'WindowsPath',
    'PortablePath'
]

import re
import os
import stat
import collections.abc
import functools
import pathlib  # since Python 3.4
from typing import Iterator, List, Optional, Pattern, Sequence, Tuple, Union


class _NativeComponents:

    def __init__(self, components: Tuple[str, ...], sep: str):
        # note: the caller has to guarantee that *components* does not contain NUL

        # - *components* has at least one element
        # - the first element is '' if and only if it represents a relative path
        # - if the first element is not '' it represents an absolute path (e.g. 'C:\\')
        # - no element except possibly the first one contains *sep*
        self._components = components
        self._sep = sep

    @property
    def components(self) -> Tuple[str, ...]:
        return self._components

    @property
    def sep(self) -> str:
        return self._sep

    def __str__(self) -> str:
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


def _native_components_for_posix(components: Tuple[str, ...]) -> _NativeComponents:
    # first element of components is '', '/', or '//'
    return _NativeComponents(components, '/')


def _native_components_for_windows(components: Tuple[str, ...]) -> _NativeComponents:
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


def _parts_from_components(components: Tuple[str, ...]) -> Tuple[str, ...]:
    if not components[0]:
        return components[1:]  # relative path
    return components  # absolute path


def _make_name_filter(f):
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


def _propagate_mtime_native(path: str, name_filter, is_dir, recurse_name_filter) -> Tuple[int, bool]:
    sr_dir = os.lstat(path)

    did_update = False

    latest_content_mtime = sr_dir.st_mtime_ns
    with os.scandir(path) as it:  # since Python 3.6
        for de in it:
            mt = latest_content_mtime

            sr = de.stat(follow_symlinks=False)
            does_match = name_filter(de.name) and (is_dir is None or stat.S_ISDIR(sr.st_mode) == is_dir)

            if stat.S_ISDIR(sr.st_mode) and not stat.S_ISLNK(sr.st_mode) and recurse_name_filter(de.name):
                mts, u = _propagate_mtime_native(de.path, name_filter, is_dir, recurse_name_filter)
                did_update = did_update or u
                if u or does_match:
                    mt = mts
            elif does_match:
                mt = sr.st_mtime_ns
            latest_content_mtime = max(latest_content_mtime, mt)

    if latest_content_mtime > sr_dir.st_mtime_ns:
        os.utime(path, ns=(sr_dir.st_atime_ns, latest_content_mtime))
        did_update = True

    return latest_content_mtime, did_update


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
    def components(self) -> Tuple[str, ...]:
        return self._native_components.components

    @property
    def parts(self) -> Tuple[str, ...]:
        return _parts_from_components(self._native_components.components)

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

    def __copy__(self):
        return self

    def __deepcopy__(self, memodict):
        return self


# https://stackoverflow.com/questions/13762231/python-metaclass-arguments
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


PathLike = Union['Path', _Native, pathlib.PurePath, str, Sequence]


@functools.total_ordering
class Path(metaclass=_PathMeta):
    def __init__(self, path: PathLike, *, is_dir: Optional[bool] = None):
        check = True

        if isinstance(path, Path):  # P(P()) must be very fast for every subclass of Path

            self._components = path._components
            self._is_dir = path._is_dir
            self._native = path._native
            check = self.__class__ is not path.__class__

        elif isinstance(path, str):  # must be very fast

            if not path:
                raise ValueError(f"invalid path: {path!r}")

            anchor = ''
            if path[0] == '/':
                anchor = '//' if path[:2] == '//' and path[:3] != '///' else '/'

            self._components = (anchor,) + tuple(c for c in path.split('/') if c and c != '.')
            self._is_dir = path[-1] == '/' or path[-2:] == '/.'
            self._native = None

        elif isinstance(path, collections.abc.Sequence):

            components = tuple(str(c) for c in path)
            if not components or components[0][:1] != '/':
                components = ('',) + components
            if components[0] not in ('', '/', '//'):
                msg = "if 'path' is a path component sequence, its first element must be one of '', '/', '//'"
                raise ValueError(msg)
            nonroot_components = tuple(c for c in components[1:] if c and c != '.')
            if any('/' in c for c in nonroot_components):
                msg = "if 'path' is a path component sequence, none except its first element must contain '/'"
                raise ValueError(msg)
            self._components = (components[0],) + nonroot_components
            self._is_dir = False
            self._native = None

        else:

            # convert
            if isinstance(path, _Native):
                self._native = path
                path = path.raw
            else:
                self._native = None

            if not isinstance(path, pathlib.PurePath):
                msg = (
                    f"'path' must be a str, dlb.fs.Path, dlb.fs.Path.Native, pathlib.PurePath, "
                    f"or a path component sequence, not {type(path)!r}"
                )
                raise TypeError(msg)

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
            check = check or self._is_dir != is_dir
            self._is_dir = is_dir

        if check:
            if any('\0' in c for c in self._components):
                raise ValueError(f"invalid path: {path!r} (must not contain NUL)")
            self._sanitize_is_dir()
            if self.__class__.__bases__ != (object,):  # dlb.fs.Path() must be fast
                self._check_constraints(False)

    def _cast(self, other: PathLike) -> 'Path':
        if other.__class__ is self.__class__:
            return other
        return self.__class__(other)

    def _sanitize_is_dir(self):
        self._is_dir = self._is_dir or len(self._components) <= 1 or self._components[-1:] == ('..',)

    def _with_components(self, components: Tuple[str, ...], *, is_dir: Optional[bool] = None,
                         components_checked: bool) -> 'Path':
        # if *components_checked* is True, each member of *component* is a component of a valid self.__class__
        # note: the caller has to guarantee that *components* does not contain NUL
        p = self.__class__(self)  # fastest way of construction
        p._components = components
        if is_dir is not None:
            p._is_dir = bool(is_dir)
        p._native = None
        p._sanitize_is_dir()
        p._check_constraints(components_checked)
        return p

    def _check_constraints(self, components_checked: bool):
        # must be fast
        try:
            for c in reversed(self.__class__.__mro__):
                # noinspection PyUnresolvedReferences
                'check_restriction_to_base' not in c.__dict__ or c.check_restriction_to_base(self, components_checked)
        except ValueError as e:
            reason = str(e)
            msg = f'invalid path for {self.__class__.__qualname__!r}: {str(self.as_string())!r}'
            if reason:
                msg = f'{msg} ({reason})'
            raise ValueError(msg) from None

    def _check_dir_list_args(self, name_filter, is_dir, recurse_name_filter, cls):
        if not self._is_dir:
            raise ValueError(f'cannot list non-directory path: {self.as_string()!r}')

        is_dir = None if is_dir is None else bool(is_dir)

        name_filter = _make_name_filter(name_filter)
        recurse_name_filter = _make_name_filter(recurse_name_filter)

        if cls is None:
            cls = self.__class__
        if not (isinstance(cls, type) and issubclass(cls, Path)):
            raise TypeError("'cls' must be None or a subclass of 'dlb.fs.Path'")

        return name_filter, is_dir, recurse_name_filter, cls

    def _check_suffix(self, suffix: str):
        if not isinstance(suffix, str):
            raise TypeError("'suffix' must be a str")
        if '/' in suffix or '\0' in suffix:
            raise ValueError(f"invalid suffix: {suffix!r}")
        if not self._components[-1] or self._components[-1] == '..':
            raise ValueError("cannot append suffix to '.' or '..' component")

    def is_dir(self) -> bool:
        return self._is_dir

    def is_absolute(self) -> bool:
        return bool(self._components[0])

    def is_normalized(self) -> bool:
        return '..' not in self._components

    def relative_to(self, other: PathLike, *, collapsable: bool = False) -> 'Path':
        other = self._cast(other)
        if not other._is_dir:
            raise ValueError(f'since {other!r} is not a directory, a path cannot be relative to it')
        n = len(other._components)
        if self._components[:n] == other._components:
            return self._with_components(('',) + self._components[n:], components_checked=True)
        if not collapsable:
            raise ValueError(f"{self.as_string()!r} does not start with {other.as_string()!r}")

        if self.is_absolute() != other.is_absolute():
            raise ValueError(f"{self.as_string()!r} cannot be relative to {other.as_string()!r}")

        # assume 'other' to be collapsable
        m = min(n, len(self._components))
        common_prefix_length = 0
        while common_prefix_length < m and \
                self._components[common_prefix_length] == other._components[common_prefix_length]:
            common_prefix_length += 1

        components = ('',) + ('..',) * (n - common_prefix_length) + self._components[common_prefix_length:]
        return self._with_components(components, components_checked=True)

    def iterdir(self, *, name_filter='', is_dir: Optional[bool] = None, recurse_name_filter=None,
                follow_symlinks: bool = True, cls=None) -> Iterator['Path']:

        name_filter, is_dir, recurse_name_filter, cls = \
            self._check_dir_list_args(name_filter, is_dir, recurse_name_filter, cls)

        dir_paths_to_recurse = [Path(self)]
        while dir_paths_to_recurse:

            dir_path = dir_paths_to_recurse.pop(0)
            with os.scandir(dir_path.native) as it:  # since Python 3.6

                paths = []
                for de in it:
                    n = de.name
                    d = de.is_dir(follow_symlinks=follow_symlinks)
                    does_match = name_filter(n) and (is_dir is None or d == is_dir)
                    do_recurse = d and recurse_name_filter(n)

                    p = dir_path / Path(n, is_dir=d) if does_match or do_recurse else None

                    if does_match:
                        paths.append(p)
                    if do_recurse:
                        dir_paths_to_recurse.append(p)

                paths.sort()
                for p in paths:
                    yield cls(p)

            dir_paths_to_recurse.sort()

    def iterdir_r(self, *, name_filter='', is_dir: Optional[bool] = None, recurse_name_filter=None,
                  follow_symlinks: bool = True, cls=None) \
            -> Iterator['Path']:
        for p in self.iterdir(name_filter=name_filter, is_dir=is_dir, recurse_name_filter=recurse_name_filter,
                              follow_symlinks=follow_symlinks, cls=cls):
            yield p.relative_to(self)

    def list(self, *, name_filter='', is_dir: Optional[bool] = None, recurse_name_filter=None,
             follow_symlinks: bool = True, cls=None) -> List['Path']:
        return sorted(self.iterdir(name_filter=name_filter, is_dir=is_dir, recurse_name_filter=recurse_name_filter,
                                   follow_symlinks=follow_symlinks, cls=cls))

    def list_r(self, *, name_filter='', is_dir: Optional[bool] = None, recurse_name_filter=None,
               follow_symlinks: bool = True, cls=None) -> List['Path']:
        return sorted(self.iterdir_r(name_filter=name_filter, is_dir=is_dir, recurse_name_filter=recurse_name_filter,
                                     follow_symlinks=follow_symlinks, cls=cls))

    def find_latest_mtime(self, *, name_filter='', recurse_name_filter=None,
                          is_dir: Optional[bool] = None, follow_symlinks: bool = True, cls=None) -> Optional['Path']:
        # must be fast for large number of objects per directory

        name_filter, is_dir, recurse_name_filter, cls = \
            self._check_dir_list_args(name_filter, is_dir, recurse_name_filter, cls)
        follow_symlinks = bool(follow_symlinks)

        latest_mtime = None
        path_with_latest_mtime = None
        path_with_latest_mtime_is_dir = False

        dir_paths_to_recurse = [str(self.native)]
        while dir_paths_to_recurse:
            dir_path = dir_paths_to_recurse.pop(0)
            with os.scandir(dir_path) as it:  # since Python 3.6
                for de in it:
                    n = de.name
                    sr = de.stat(follow_symlinks=follow_symlinks)
                    d = stat.S_ISDIR(sr.st_mode)

                    if name_filter(n) and (is_dir is None or d == is_dir):
                        mt = sr.st_mtime_ns
                        if latest_mtime is None or mt > latest_mtime:
                            latest_mtime = mt
                            path_with_latest_mtime = de.path
                            path_with_latest_mtime_is_dir = d
                        elif mt == latest_mtime and de.path < path_with_latest_mtime:
                            path_with_latest_mtime = de.path
                            path_with_latest_mtime_is_dir = d

                    if d and not (stat.S_ISLNK(sr.st_mode) and not follow_symlinks) and recurse_name_filter(n):
                        dir_paths_to_recurse.append(de.path)

        if not path_with_latest_mtime:
            return

        return cls(_Native(path_with_latest_mtime), is_dir=path_with_latest_mtime_is_dir)

    def propagate_mtime(self, *, name_filter='', is_dir: Optional[bool] = None,
                        recurse_name_filter='') -> Optional[int]:
        # must be fast

        name_filter, is_dir, recurse_name_filter, cls = \
            self._check_dir_list_args(name_filter, is_dir, recurse_name_filter, None)

        abs_path = str(self.native)
        if not self.is_absolute():
            abs_path = os.path.join(os.getcwd(), abs_path)

        mtime_ns, did_update = _propagate_mtime_native(abs_path, name_filter, is_dir, recurse_name_filter)
        return mtime_ns if did_update else None

    @property
    def components(self) -> Tuple[str, ...]:
        # first element is '/' or '//' if absolute and '' otherwise
        return self._components

    @property
    def parts(self) -> Tuple[str, ...]:
        # first element: '/' or '//' if absolute, does not start with '/' otherwise
        return _parts_from_components(self._components)

    def with_appended_suffix(self, suffix: str) -> 'Path':
        self._check_suffix(suffix)
        return self._with_components(self._components[:-1] + (self._components[-1] + suffix,), components_checked=False)

    def with_replacing_suffix(self, suffix: str) -> 'Path':
        self._check_suffix(suffix)
        name, ext = os.path.splitext(self._components[-1])
        if not ext:
            raise ValueError(f'does not contain an extension suffix')
        return self._with_components(self._components[:-1] + (name + suffix,), components_checked=False)

    @property
    def pure_posix(self) -> pathlib.PurePosixPath:
        return pathlib.PurePosixPath(self._as_string())

    @property
    def pure_windows(self) -> pathlib.PureWindowsPath:
        # construction from one string is much faster than several components (its also safer)
        p = pathlib.PureWindowsPath(str(_native_components_for_windows(self.components)))
        if p.is_reserved():
            # not actually reserved for directory path but information whether directory is lost after conversion
            raise ValueError(f'path is reserved')
        return p

    @property
    def native(self):
        # must be fast
        if self._native is None:
            self._native = _Native(_native_components(self.components))  # does _not_ check restrictions again
        return self._native

    def _as_string(self) -> str:
        c = self._components
        if not c[0]:
            c = c[1:]  # relative
        elif len(c) > 1:
            c = (c[0] + c[1],) + c[2:]
        return '/'.join(c) if c else '.'

    def as_string(self) -> str:
        s = self._as_string()
        if not self._is_dir or s[-1] == '/':
            return s
        return s + '/'

    def __truediv__(self, other: PathLike) -> 'Path':
        if not self._is_dir:
            raise ValueError(f'cannot append to non-directory path: {self!r}')
        other = self._cast(other)
        o = other._components
        if o[0]:
            raise ValueError(f'cannot append absolute path: {other!r}')
        if len(o) <= 1:
            return self
        return self._with_components(self._components + o[1:], is_dir=other._is_dir, components_checked=True)

    # note: there is no __rtruediv__ on purpuse

    def __eq__(self, other: PathLike) -> bool:
        # on all platform, comparison is case sensitive
        other = self._cast(other)
        return (self._components, self._is_dir) == (other._components, other._is_dir)

    def __lt__(self, other: PathLike) -> bool:
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

    def __getitem__(self, item) -> 'Path':
        if not isinstance(item, slice):
            raise TypeError("slice of part indices expected (use 'parts' for single components)")

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
        return self._with_components(components, is_dir=stop < n or self._is_dir, components_checked=True)


class RelativePath(Path):
    def check_restriction_to_base(self, components_checked: bool):
        if self.is_absolute():
            raise ValueError('must be relative')


class AbsolutePath(Path):
    # noinspection PyUnusedLocal
    def check_restriction_to_base(self, components_checked: bool):
        if not self.is_absolute():
            raise ValueError('must be absolute')


class NormalizedPath(Path):
    # noinspection PyUnusedLocal
    def check_restriction_to_base(self, components_checked: bool):
        if not self.is_normalized():
            raise ValueError('must be normalized')


class NoSpacePath(Path):
    def check_restriction_to_base(self, components_checked: bool):
        if not components_checked and any(' ' in c for c in self.parts):
            raise ValueError('must not contain space')


class PosixPath(Path):
    pass


class PortablePosixPath(PosixPath):
    MAX_COMPONENT_LENGTH = 14  # {_POSIX_NAME_MAX}
    MAX_PATH_LENGTH = 255  # {_POSIX_PATH_MAX} - 1
    CHARACTERS = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-')

    def check_restriction_to_base(self, components_checked: bool):

        # IEEE Std 1003.1-2008, 4.13 Pathname Resolution:
        #
        #   If a pathname begins with two successive <slash> characters, the first component following the
        #   leading <slash> characters may be interpreted in an implementation-defined manner, although more
        #   than two leading <slash> characters shall be treated as a single <slash> character.

        components = self.components
        if components[0] == '//':
            raise ValueError("non-standardized component starting with '//' not allowed")

        if not components_checked:
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
        if self._is_dir and (len(components) > 1 or components[0]):
            n += 1
        if n > self.MAX_PATH_LENGTH:
            raise ValueError(f'must not contain more than {self.MAX_PATH_LENGTH} characters')


class WindowsPath(Path):
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
    RESERVED_CHARACTERS = frozenset('\\"|?*<>:')  # besides: '/'

    # from pathlib._WindowsFlavour.reserved_names of Python 3.7.3
    RESERVED_AS_LAST_COMPONENT = (
        {'CON', 'PRN', 'AUX', 'NUL'} | {'COM%d' % i for i in range(1, 10)} | {'LPT%d' % i for i in range(1, 10)}
    )

    def check_restriction_to_base(self, components_checked: bool):
        # unfortunately, there is not official way to access flaviour specifics without contructing a path object

        parts = _native_components_for_windows(self.components).components
        if not parts[0]:
            parts = parts[1:]
        if parts and parts[-1].upper() in self.RESERVED_AS_LAST_COMPONENT:
            # not actually reserved for directory path but information whether directory is lost after conversion
            raise ValueError(f'path is reserved')

        if not components_checked:
            # without already checked in _native_components_for_windows()
            reserved = self.RESERVED_CHARACTERS - frozenset('\\:')

            for c in parts:
                invalid_characters = set(c) & reserved
                if invalid_characters:
                    raise ValueError("must not contain reserved characters: {0}".format(
                        ','.join(repr(c) for c in sorted(invalid_characters))))

                # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
                min_codepoint = ord(min(c))
                if min_codepoint < 0x20:
                    raise ValueError(f'must not contain characters with codepoint lower '
                                     f'than U+0020: U+{min_codepoint:04X}')

                max_codepoint = ord(max(c))
                if max_codepoint > 0xFFFF:
                    raise ValueError(f'must not contain characters with codepoint '
                                     f'higher than U+FFFF: U+{max_codepoint:04X}')


class PortableWindowsPath(WindowsPath):
    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247(v=vs.85).aspx#maxpath
    MAX_COMPONENT_LENGTH = 255  # lpMaximumComponentLength
    MAX_PATH_LENGTH = 259  # MAX_PATH - 1

    def check_restriction_to_base(self, components_checked: bool):
        components = self.components

        if not components_checked:
            for c in components[1:]:
                if len(c) > self.MAX_COMPONENT_LENGTH:
                    raise ValueError(f'component must not contain more than {self.MAX_COMPONENT_LENGTH} characters')
                if c != '..' and c[-1] in ' .':
                    # https://msdn.microsoft.com/en-us/library/windows/desktop/aa365247%28v=vs.85%29.aspx#naming_conventions
                    raise ValueError("component must not end with ' ' or '.'")

        n = sum(len(c) for c in components) + max(0, len(components) - 2)
        if self._is_dir and (len(components) > 1 or components[0]):
            n += 1

        if n > self.MAX_PATH_LENGTH:
            raise ValueError(f'must not contain more than {self.MAX_PATH_LENGTH} characters')


class PortablePath(PortablePosixPath, PortableWindowsPath, RelativePath):
    pass
