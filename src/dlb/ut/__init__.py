# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""(Technical) utilities.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = []

import marshal
import dataclasses
import collections.abc
from typing import Any, Dict, Iterable

non_container_fundamental_types = (bool, int, float, complex, str, bytes)


# is obj of an immutable built-in type that is no container (except str, bytes)?
def is_immutable_fundamental(obj):
    return obj is None or isinstance(obj, non_container_fundamental_types)


def _make_fundamental(obj, repeatable):
    if repeatable:
        if isinstance(obj, str):
            # https://medium.com/@bdov_/https-medium-com-bdov-python-objects-part-iii-string-interning-625d3c7319de
            # CPython implementation of marshal.dumps(): https://github.com/python/cpython/blob/master/Python/marshal.c
            return b's' + obj.encode()
        elif isinstance(obj, bytes):
            return b'b' + obj

    if is_immutable_fundamental(obj):
        return obj

    r = repeatable

    if isinstance(obj, collections.abc.Mapping):  # note: loses order of collections.OrderedDict
        if r:
            return tuple(sorted((_make_fundamental(k, r), _make_fundamental(v, r)) for k, v in obj.items()))
        return {_make_fundamental(k, r): _make_fundamental(v, r) for k, v in obj.items()}

    if isinstance(obj, (set, frozenset)):
        obj = frozenset(_make_fundamental(k, r) for k in obj)
        if not r:
            return obj
        return tuple(sorted(obj))

    if isinstance(obj, collections.abc.Iterable):
        return tuple(_make_fundamental(k, r) for k in obj)

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.astuple(obj)

    raise TypeError


def make_fundamental(obj, repeatable=False):
    try:
        # note: isinstance() can lead to infinite recursion, aborted by RecursionError
        return _make_fundamental(obj, repeatable)
    except (TypeError, ValueError, RecursionError):
        raise TypeError from None


def to_permanent_local_bytes(obj) -> bytes:
    # For the same *obj*, the return value is the same for different interpreter processes as long as
    # the components of 'dlb.ex._platform.PERMANENT_PLATFORM_ID' do not change.
    #
    # The following types of objects are not (the types on each line are represented indistinguishably):
    #
    #   - iterables that are not are not of type 'bytes', 'str'
    #   - collections.abc.Mapping
    #   - collections.abc.Mapping and their sorted item tuples
    #   - dataclass instances and their tuple representation

    return marshal.dumps(make_fundamental(obj, True), 4)


def set_module_name_to_parent(cls):  # e.g. dlb.ex._context.Context -> dlb.ex.Context
    cls.__module__ = '.'.join(cls.__module__.split('.')[:-1])


def set_module_name_to_parent_by_name(obj_by_name: Dict[str, Any], names: Iterable):
    for name in names:
        obj = obj_by_name[name]
        obj.__module__ = '.'.join(obj.__module__.split('.')[:-1])


def exception_to_line(exc: BaseException, force_classname: bool = False):
    first_line = str(exc)
    if first_line:
        first_line = first_line.splitlines()[0].replace('\t', ' ').strip()  # only first line

    parts = []
    if force_classname or not first_line:
        cls = exc.__class__
        parts.append(f'{cls.__module__}.{cls.__qualname__}')
    if first_line:
        parts.append(first_line)

    return ': '.join(parts)


def format_time_ns(time_ns: int, number_of_decimal_places: int = 9) -> str:
    # Return a string representation for a time in seconds. The time *time_ns* is given in nanoseconds.
    # It is exact for *number_of_decimal_places* >= 9 and rounded towards 0 for *number_of_decimal_places* < 9.

    time_ns = int(time_ns)
    if time_ns < 0:
        return '-' + format_time_ns(-time_ns, number_of_decimal_places)  # -0.0... is possible

    s = str(time_ns).rjust(10, '0')
    i = len(s) - 9
    s = s[:i] + '.' + s[i:]  # has exactly 9 decimal places

    number_of_decimal_places = max(1, int(number_of_decimal_places))
    m = number_of_decimal_places - 9  # number of decimal places to remove
    if m >= 0:
        return s + '0' * m
    return s[:m]  # round towards zero
