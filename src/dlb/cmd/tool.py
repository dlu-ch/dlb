import re
import dlb.fs

EXECUTION_PARAMETER_NAME_REGEX = re.compile('^[A-Z][A-Z0-9]*(_[A-Z][A-Z0-9]*)*$')
assert EXECUTION_PARAMETER_NAME_REGEX.match('A')
assert EXECUTION_PARAMETER_NAME_REGEX.match('A2_B')
assert not EXECUTION_PARAMETER_NAME_REGEX.match('_A')

DEPENDENCY_NAME_REGEX = re.compile('^[a-z][a-z0-9]*(_[a-z][a-z0-9]*)*$')
assert DEPENDENCY_NAME_REGEX.match('object_file')
assert not DEPENDENCY_NAME_REGEX.match('_object_file_')
assert not DEPENDENCY_NAME_REGEX.match('Object_file_')

RESERVED_NAME_REGEX = re.compile('^__[^_].*[^_]?__$')
assert RESERVED_NAME_REGEX.match('__init__')
assert not RESERVED_NAME_REGEX.match('__init')


__all__ = ['Tool']


class _ConcreteDependencyMixinMeta(type):

    @property
    def multiplicity(cls):
        return cls._multiplicity

    def __getitem__(cls, multiplicity):
        if cls.multiplicity is not None:
            raise TypeError('dependency role with multiplicity is not subscriptable')

        if isinstance(multiplicity, int):
            multiplicity = slice(multiplicity, multiplicity + 1)
        elif not isinstance(multiplicity, slice):
            raise TypeError("dependency role multiplicity must be int oder slice of int")

        step = 1 if multiplicity.step is None else int(multiplicity.step)
        if step <= 0:
            raise ValueError('slice step must be positive')
        start = 0 if multiplicity.start is None else int(multiplicity.start)
        if start < 0:
            raise ValueError('minimum multiplicity (start of slice) must be non-negative')
        stop = None if multiplicity.stop is None else max(start, int(multiplicity.stop))

        if stop is not None:
            # make stop the maximum + 1
            stop = ((stop - start - 1) // step) * step + start + 1

        if stop is not None and start < stop <= start + step:  # is start the only element?
            stop = start + 1
            step = 1
        if stop == start:
            start = 0
            stop = 1

        assert start >= 0
        assert stop is None or stop > start
        assert step > 0

        class MultipleDependency(_MultipleDependencyBase):
            _element_dependency = cls
            _multiplicity = slice(start, stop, step)

        if stop is not None and stop == start + 1:
            suffix = str(start)
        else:
            suffix = (str(start) if start else '') + ':' + (str(stop) if stop is not None else '')
            if step > 1:
                suffix += ':' + str(step)
        suffix = '[{}]'.format(suffix)

        MultipleDependency.__name__ = cls.__name__ + suffix
        MultipleDependency.__qualname__ = cls.__qualname__ + suffix

        return MultipleDependency


# list this as last class before abstract dependency class in base class list
class _ConcreteDependencyMixin(metaclass=_ConcreteDependencyMixinMeta):
    #: None or slice.
    #: if slice: Exactly every multiplicity which is contained in this slice is valid (step must not be non-positive)
    _multiplicity = None

    def __init__(self, is_required=True):
        self._is_required = is_required

    @property
    def is_required(self):
        # TODO: document
        return self._is_required

    def is_more_restrictive_than(self, other):
        return isinstance(self, other.__class__) \
               and not (other.is_required and not self.is_required) \
               and (self.__class__.multiplicity is None) == (other.__class__.multiplicity is None)

    @classmethod
    def _check_multiplicity(cls, n):
        m = cls.multiplicity
        if m is None:
            if n is not None:
                raise ValueError('dependency role has no multiplicity')
        else:
            if n < m.start:
                raise ValueError('value has {} elements, but minimum multiplicity is {}'.format(n, m.start))
            if m.stop is not None and n >= m.stop:
                raise ValueError('value has {} elements, but maximum multiplicity is {}'.format(n, m.stop - 1))
            if (n - m.start) % m.step != 0:
                raise ValueError(
                    'value has {} elements, but multiplicity must be an integer multiple of {} above {}'
                    .format(n, m.step, m.start))

    @classmethod
    def is_multiplicity_valid(cls, n):
        # TODO: document
        if not (n is None or isinstance(n, int)):
            raise TypeError('multiplicity must be None or integer')
        try:
            cls._check_multiplicity(n)
        except ValueError:
            return False
        return True

    def validate(self, value):
        # do _not_ call super().validate() here!
        if self.is_required and value is None:
            raise ValueError('required dependency must not be None')
        return value


# noinspection PyUnresolvedReferences,PyArgumentList
class _PathDependencyMixin:
    def __init__(self, cls=dlb.fs.Path, **kwargs):
        super().__init__(**kwargs)
        if not (isinstance(cls, type) and issubclass(cls, dlb.fs.Path)):
            raise TypeError("'cls' is not a subclass of 'dlb.fs.Path'")
        self._path_cls = cls

    def is_more_restrictive_than(self, other):
        return super().is_more_restrictive_than(other) and issubclass(self._path_cls, other._path_cls)

    def validate(self, value):
        value = super().validate(value)
        return self._path_cls(value) if value is not None else None


class _DirectoryDependencyMixin(_PathDependencyMixin):
    def validate(self, value):
        value = super().validate(value)
        if value is not None and not value.is_dir():
            raise ValueError('non-directory path not valid for directory dependency: {}'.format(repr(value)))
        return value


class _NonDirectoryDependencyMixin(_PathDependencyMixin):
    def validate(self, value):
        value = super().validate(value)
        if value is not None and value.is_dir():
            raise ValueError('directory path not valid for non-directory dependency: {}'.format(repr(value)))
        return value


class _Dependency():
    #: Rank for ordering (the higher the rank, the earlier the dependency is needed)
    RANK = 0


# noinspection PyAbstractClass
class _InputDependency(_Dependency):
    RANK = 3


# noinspection PyAbstractClass
class _IntermediateDependency(_Dependency):
    RANK = 2


# noinspection PyAbstractClass
class _OutputDependency(_Dependency):
    RANK = 1


class _MultipleDependencyBase(_ConcreteDependencyMixin, _Dependency):
    #: Subclass of _Dependency for each element
    _element_dependency = None

    def __init__(self, is_required=True, is_duplicate_free=False, **kwargs):
        super().__init__(is_required=is_required)
        self._is_duplicate_free = is_duplicate_free
        # noinspection PyCallingNonCallable
        self._element_prototype = self.__class__._element_dependency(is_required=True, **kwargs)

    def validate(self, value):
        value = super().validate(value)

        if self.__class__.multiplicity is not None and isinstance(value, str):  # for safety
            raise TypeError('since dependency role has a multiplicity, value must be iterable (other than string)')
        value = tuple(self._element_prototype.validate(v) for v in value)

        self.__class__._check_multiplicity(len(value))

        if self._is_duplicate_free:
            prefix = []
            for v in value:
                if v in prefix:
                    raise ValueError(
                        'dependency must be duplicate-free, but contains {} more than once'.format(repr(v)))
                prefix.append(v)

        return value

    def is_more_restrictive_than(self, other):
        # only compare if multiplicity os None or not
        return super().is_more_restrictive_than(other) \
               and self._element_prototype.is_more_restrictive_than(other._element_prototype)


class _RegularInputFileDependency(_NonDirectoryDependencyMixin, _ConcreteDependencyMixin, _InputDependency):
    pass


class _InputDirectoryDependency(_DirectoryDependencyMixin, _ConcreteDependencyMixin, _InputDependency):
    pass


class _RegularOutputFileDependency(_NonDirectoryDependencyMixin, _ConcreteDependencyMixin, _OutputDependency):
    pass


class _OutputDirectoryDependency(_DirectoryDependencyMixin, _ConcreteDependencyMixin, _OutputDependency):
    pass


# noinspection PyProtectedMember,PyUnresolvedReferences
class _ToolBase:

    def __init__(self, **kwargs):
        super().__init__()

        dependency_names = self.__class__._dependency_names
        assigned_names = set()

        for name, value in kwargs.items():
            try:
                role = getattr(self.__class__, name)
            except AttributeError:
                raise TypeError(
                    '{} is not a dependency role of {}: {}'.format(
                        repr(name),
                        repr(self.__class__.__qualname__),
                        ', '.join(repr(n) for n in dependency_names))) from None
            object.__setattr__(self, name, role.validate(value))
            assigned_names.add(name)

        for name in sorted(set(dependency_names) - assigned_names):
            role = getattr(self.__class__, name)
            if role.is_required:
                raise TypeError("missing keyword parameter for dependency role: {}".format(repr(name)))
            object.__setattr__(self, name, None)

    def __setattr__(self, name, value):
        raise AttributeError

    def __delattr__(self, name):
        raise AttributeError

    def __repr__(self):
        names = self.__class__._dependency_names
        args = ', '.join('{}={}'.format(n, repr(getattr(self, n))) for n in names)
        return '{}({})'.format(self.__class__.__qualname__, args)


def _inject_nested_class_into(owner, cls, name, owner_qualname=None):
    setattr(owner, name, cls)
    cls.__name__ = name
    if owner_qualname is None:
        owner_qualname = owner.__qualname__
    cls.__qualname__ = owner_qualname + '.' + name


# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase, _Dependency, 'Dependency', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase, _InputDependency, 'Input', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase, _OutputDependency, 'Output', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase, _IntermediateDependency, 'Intermediate', 'Tool')

# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Input, _RegularInputFileDependency, 'RegularFile')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Input, _InputDirectoryDependency, 'Directory')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Output, _RegularOutputFileDependency, 'RegularFile')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Output, _OutputDirectoryDependency, 'Directory')

del _inject_nested_class_into


class _ToolMeta(type):

    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)

        # prevent attributes of _ToolBase from being overridden
        protected_attribs = (set(_ToolBase.__dict__.keys()) - {'__doc__', '__module__'} | {'__new__'})
        attribs = set(cls.__dict__) & protected_attribs
        if attribs:
            raise AttributeError("must not be overridden in a 'dlb.cmd.Tool': {}".format(repr(sorted(attribs)[0])))

        cls.check_own_attributes()
        super().__setattr__('_dependency_names', cls._get_dependency_names())

    def check_own_attributes(cls):
        for name, value in cls.__dict__.items():
            if RESERVED_NAME_REGEX.match(name):
                pass
            elif EXECUTION_PARAMETER_NAME_REGEX.match(name):
                # if overridden: must be instance of type of overridden attribute
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not isinstance(value, type(base_value)):
                        raise TypeError(
                            "attribute {} of base class may only be overridden with a value which is a {}"
                            .format(repr(name), repr(type(base_value))))
            elif DEPENDENCY_NAME_REGEX.match(name):
                if not (isinstance(value, _ToolBase.Dependency) and isinstance(value, _ConcreteDependencyMixin)):
                    raise TypeError(
                        "the value of {} must be an instance of a concrete subclass of 'dlb.cmd.Tool.Dependency'"
                        .format(repr(name)))
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not value.is_more_restrictive_than(base_value):
                        raise TypeError(
                            "attribute {} of base class may only be overridden by a {} at least as restrictive"
                            .format(repr(name), repr(type(base_value))))
            else:
                raise AttributeError((
                    "invalid class attribute name: {} "
                    "(every class attribute of a 'dlb.cmd.Tool' must be named "
                    "like 'UPPER_CASE_WORD' or 'lower_case_word)").format(repr(name)))

    def _get_dependency_names(cls):
        dependencies = {n: getattr(cls, n) for n in dir(cls) if DEPENDENCY_NAME_REGEX.match(n)}
        pairs = [(-v.RANK, not v.is_required, n) for n, v in dependencies.items() if isinstance(v, Tool.Dependency)]
        pairs.sort()
        # order: input - intermediate - output, required first
        return tuple(p[-1] for p in pairs)

    def __setattr__(cls, name, value):
        raise AttributeError

    def __delattr__(cls, name):
        raise AttributeError


class Tool(_ToolBase, metaclass=_ToolMeta):
    pass
