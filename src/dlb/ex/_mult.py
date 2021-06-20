# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Representation of multiplicity by subscripting classes, e.g. T[2:].
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = []

import re
from typing import Optional, Union


class MultiplicityRange:
    # Describes a set of multiplicity by an integer or a slice of integers.
    #
    # If MultiplicityRange(m) is valid:
    # An integer ``n`` is considered a multiplicity in the range iff ``n in [i for i in range(n + 1)[m]``.

    def __init__(self, multiplicity: Union[int, slice]):
        if isinstance(multiplicity, int):
            multiplicity = slice(multiplicity, multiplicity + 1)

        try:
            if not isinstance(multiplicity, slice):
                raise TypeError
            start = multiplicity.start
            stop = multiplicity.stop
            step = multiplicity.step
            if not all(e is None or isinstance(e, int) for e in (start, stop, step)):
                raise TypeError
        except TypeError:
            raise TypeError(f"'multiplicity' must be int or slice of int, not {multiplicity!r}") from None

        step = 1 if step is None else step
        if step <= 0:
            raise ValueError(f'slice step must be positive, not {step}')

        start = 0 if start is None else start
        if start < 0:
            raise ValueError(f'minimum multiplicity (start of slice) must be non-negative, not {start}')

        if stop is not None and stop < 0:
            raise ValueError(f'upper multiplicity bound (stop of slice) must be non-negative, not {stop}')

        if stop is not None:
            if stop > start:
                c = (stop - start - 1) // step  # number of repetitions (except start)
                stop = c * step + start + 1  # make stop the maximum + 1
                if c == 0:
                    stop = start + 1
                    step = 1
            else:  # empty
                start = 0
                stop = 0
                step = 1

        self._slice = slice(start, stop, step)

    def __contains__(self, count):
        if not isinstance(count, int):
            raise TypeError("'count' must be integer")

        s = self._slice
        if count < s.start:
            return False
        if s.stop is not None and count >= s.stop:
            return False
        if (count - s.start) % s.step != 0:
            return False

        return True

    @property
    def as_slice(self):
        return self._slice

    def __eq__(self, other):
        return self.as_slice == other.as_slice

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        s = self._slice

        if s.stop is not None and s.stop == s.start + 1:
            suffix = str(s.start)  # exactly one member
        else:
            suffix = (str(s.start) if s.start else '') + ':' + (str(s.stop) if s.stop is not None else '')
            if s.step > 1:
                suffix += ':' + str(s.step)

        return f'[{suffix}]'

    def __repr__(self):
        return f"{self.__class__.__name__}({self._slice})"


class _MultiplicityHolderProxy:
    def __init__(self, element_class: type, multiplicity: Optional[MultiplicityRange]):
        self._element_class = element_class
        self._multiplicity = multiplicity
        s = '' if multiplicity is None else str(multiplicity)
        self.__name__ = element_class.__name__ + s
        self.__qualname__ = element_class.__qualname__ + s

    @property
    def element_class(self):
        return self._element_class

    def __call__(self, *args, **kwargs):  # simulate a constructor call
        element = self._element_class.__new__(self._element_class, *args, **kwargs)
        if isinstance(element, self._element_class):
            element._multiplicity = self._multiplicity
            element.__init__(*args, **kwargs)
        return element

    def __getitem__(self, multiplicity):
        raise TypeError(f'{self._element_class.__name__!r} with multiplicity is not subscriptable')

    def __repr__(self):
        multiplicity_suffix = f"{self._element_class!r} with multiplicity {self._multiplicity}"
        g = re.fullmatch('<(.+)>|(.+)', super().__repr__()).groups()
        proxy = g[0] or g[1]
        return f"<{proxy} for {multiplicity_suffix}>"


class _MultiplicityHolderMeta(type):
    def __getitem__(cls, multiplicity: Union[int, slice]) -> _MultiplicityHolderProxy:
        return _MultiplicityHolderProxy(cls, MultiplicityRange(multiplicity))


class MultiplicityHolder(metaclass=_MultiplicityHolderMeta):
    # A subclass T of _Multiplicity can be instantiated like this:
    #
    #   T(a=1)     ->   instance t of T with t.multiplicity = None
    #   T[m](a=1)  ->   instance t of T with t.multiplicity = Multiplicity(m)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if '_multiplicity' not in self.__dict__:
            self._multiplicity = None

    @property
    def multiplicity(self):
        return self._multiplicity
