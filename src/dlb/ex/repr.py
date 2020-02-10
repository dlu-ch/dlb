import sys
import collections.abc
assert sys.version_info >= (3, 6)

__all__ = []


_non_container_fundamental_types = (bool, int, float, complex, str, bytes)


# is obj of an immutable built-in type that is no container (except str, bytes)?
def is_immutable_fundamental(obj):
    return obj is None or isinstance(obj, _non_container_fundamental_types)


def _make_fundamental(obj, remaining_depth, force_ordered):
    if remaining_depth <= 0:
        raise ValueError

    if is_immutable_fundamental(obj):
        return obj

    n = remaining_depth - 1
    o = force_ordered

    if isinstance(obj, collections.abc.Mapping):  # note: loses order of collections.OrderedDict
        if o:
            return tuple(sorted((_make_fundamental(k, n, o), _make_fundamental(v, n, o)) for k, v in obj.items()))
        return {_make_fundamental(k, n, o): _make_fundamental(v, n, o) for k, v in obj.items()}

    if isinstance(obj, (set, frozenset)):
        obj = frozenset(_make_fundamental(k, n, o) for k in obj)
        if not o:
            return obj
        return tuple(sorted(obj))

    if isinstance(obj, collections.abc.Iterable):
        return tuple(_make_fundamental(k, n, o) for k in obj)

    raise TypeError


def make_fundamental(obj, replace_unordered_by_tuple=False):
    max_nesting_depth = 1001
    try:
        return _make_fundamental(obj, max_nesting_depth, replace_unordered_by_tuple)
    except:
        f = ', '.join(repr(c.__name__) for c in _non_container_fundamental_types)
        msg = (
            f"cannot be made fundamental: {obj!r}\n"
            f"  | an object is fundamental if it is 'None', or of type {f}, "
            f"or an iterable of only such objects (nested to at most {max_nesting_depth} levels)"
        )
        raise TypeError(msg) from None
