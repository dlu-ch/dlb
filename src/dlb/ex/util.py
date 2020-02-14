# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""(Technical) utilities.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = ('is_immutable_fundamental', 'make_fundamental')

import sys
import collections.abc
import typing
assert sys.version_info >= (3, 6)


_non_container_fundamental_types = (bool, int, float, complex, str, bytes)


# is obj of an immutable built-in type that is no container (except str, bytes)?
def is_immutable_fundamental(obj):
    return obj is None or isinstance(obj, _non_container_fundamental_types)


def _make_fundamental(obj, force_ordered):
    if is_immutable_fundamental(obj):
        return obj

    o = force_ordered

    if isinstance(obj, collections.abc.Mapping):  # note: loses order of collections.OrderedDict
        if o:
            return tuple(sorted((_make_fundamental(k, o), _make_fundamental(v, o)) for k, v in obj.items()))
        return {_make_fundamental(k, o): _make_fundamental(v, o) for k, v in obj.items()}

    if isinstance(obj, (set, frozenset)):
        obj = frozenset(_make_fundamental(k, o) for k in obj)
        if not o:
            return obj
        return tuple(sorted(obj))

    if isinstance(obj, collections.abc.Iterable):
        return tuple(_make_fundamental(k, o) for k in obj)

    raise TypeError


def make_fundamental(obj, replace_unordered_by_tuple=False):
    try:
        # note: isinstance() can lead to infinite recursion, aborted by RecursionError
        return _make_fundamental(obj, replace_unordered_by_tuple)
    except (TypeError, ValueError, RecursionError):
        f = ', '.join(repr(c.__name__) for c in _non_container_fundamental_types)
        msg = (
            f"cannot be made fundamental: {obj!r}\n"
            f"  | an object is fundamental if it is 'None', or of type {f}, "
            f"or an iterable of only such objects"
        )
        raise TypeError(msg) from None


def set_module_name_to_parent(cls):  # e.g. dlb.ex.context.Context -> dlb.ex.Context
    cls.__module__ = '.'.join(cls.__module__.split('.')[:-1])


def set_module_name_to_parent_by_name(obj_by_name: typing.Dict[str, typing.Any], names: typing.Iterable):
    for name in names:
        obj = obj_by_name[name]
        obj.__module__ = '.'.join(obj.__module__.split('.')[:-1])


def exception_to_line(exc: Exception, force_classname: bool = False):
    first_line = str(exc)
    if first_line:
        first_line = first_line.splitlines()[0].replace('\t', ' ').strip()  # only first line

    parts = []
    if force_classname or not first_line:
        parts.append('.'.join([exc.__class__.__module__, exc.__class__.__qualname__]))
    if first_line:
        parts.append(first_line)

    return ': '.join(parts)
