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


class _Dependency:
    #: Rank for ordering (the higher the rank, the earlier the dependency is needed)
    RANK = 0

    def __init__(self, is_required=True):
        self._is_required = is_required

    @property
    def is_required(self):
        return self._is_required

    def is_superset_of(self, other):
        # TODO: test
        return isinstance(other, self.__class__)

    def validate(self, value):
        raise NotImplementedError


# noinspection PyAbstractClass
class _OutputDependency(_Dependency):
    RANK = 1


# noinspection PyAbstractClass
class _IntermediateDependency(_Dependency):
    RANK = 2


# noinspection PyAbstractClass
class _InputDependency(_Dependency):
    RANK = 3


# list this as last class before abstract dependency class in base class list
class _ConcreteDependencyMixin:
    def validate(self, value):
        # do _not_ call super().validate() here!
        if self.is_required and value is None:
            raise ValueError('required dependency must not be None')
        return value


# noinspection PyUnresolvedReferences,PyArgumentList
class _PathDependencyMixin:
    def __init__(self, cls=dlb.fs.Path, **kwargs):
        super().__init__(**kwargs)
        if not issubclass(cls, dlb.fs.Path):
            raise TypeError("'cls' is not a subclass of 'dlb.fs.Path'")
        self._path_cls = cls

    def is_superset_of(self, other):
        return super().is_superset_of(other) and issubclass(other._path_cls, self._path_cls)

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


class _RegularInputFileDependency(_NonDirectoryDependencyMixin, _ConcreteDependencyMixin, _InputDependency):
    pass


class _InputDirectoryDependency(_DirectoryDependencyMixin, _ConcreteDependencyMixin, _InputDependency):
    pass


class _RegularOutputFileDependency(_NonDirectoryDependencyMixin, _ConcreteDependencyMixin, _OutputDependency):
    pass


class _OutputDirectoryDependency(_DirectoryDependencyMixin, _ConcreteDependencyMixin, _OutputDependency):
    pass


# noinspection PyProtectedMember,PyUnresolvedReferences
class _BaseTool:

    def __init__(self, **kwargs):
        super().__init__()

        dependency_names = self.__class__._dependency_names
        assigned_names = set()

        for name, value in kwargs.items():
            try:
                role = getattr(self.__class__, name)
            except AttributeError:
                raise TypeError(
                    '{} is not a dependency role of {} (these are: {})'.format(
                        repr(name),
                        repr(self.__class__.__qualname__),
                        ', '.join(repr(n) for n in dependency_names))) from None
            object.__setattr__(self, name, role.validate(value))
            assigned_names.add(name)

        for name in sorted(set(dependency_names) - assigned_names):
            role = getattr(self.__class__, name)
            if role.is_required:
                raise TypeError("missing keyword parameter for dependency role {}".format(repr(name)))
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
_inject_nested_class_into(_BaseTool, _Dependency, 'Dependency', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_BaseTool, _InputDependency, 'Input', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_BaseTool, _OutputDependency, 'Output', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_BaseTool, _IntermediateDependency, 'Intermediate', 'Tool')

# noinspection PyTypeChecker
_inject_nested_class_into(_BaseTool.Input, _RegularInputFileDependency, 'RegularFile')
# noinspection PyTypeChecker
_inject_nested_class_into(_BaseTool.Input, _InputDirectoryDependency, 'Directory')
# noinspection PyTypeChecker
_inject_nested_class_into(_BaseTool.Output, _RegularOutputFileDependency, 'RegularFile')
# noinspection PyTypeChecker
_inject_nested_class_into(_BaseTool.Output, _OutputDirectoryDependency, 'Directory')

del _inject_nested_class_into


class _ToolMeta(type):

    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)

        # prevent attributes of _BaseTool from being overwritten
        protected_attribs = (set(_BaseTool.__dict__.keys()) - {'__doc__', '__module__'} | {'__new__'})
        attribs = set(cls.__dict__) & protected_attribs
        if attribs:
            raise AttributeError("must not be overwritten in a 'dlb.cmd.Tool': {}".format(repr(sorted(attribs)[0])))

        cls.check_own_attributes()
        super().__setattr__('_dependency_names', cls._get_dependency_names())

    def check_own_attributes(cls):
        for name, value in cls.__dict__.items():
            if RESERVED_NAME_REGEX.match(name):
                pass
            elif EXECUTION_PARAMETER_NAME_REGEX.match(name):
                # if overwritten: must be instance of type of overwritten attribute
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not isinstance(value, type(base_value)):
                        raise TypeError(
                            "class {c} overwrites attribute {a} of class {b} with a value which is not a {t}".format(
                                b=repr(base_class.__qualname__), c=repr(cls.__qualname__), a=repr(name),
                                t=repr(type(base_value))))
            elif DEPENDENCY_NAME_REGEX.match(name):
                if not (isinstance(value, _BaseTool.Dependency) and type(value) != _BaseTool.Dependency):
                    raise TypeError(
                        "the value of {} must be an instance of a (strict) subclass of 'dlb.cmd.Tool.Dependency'"
                        .format(repr(name)))
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not base_value.is_superset_of(value):
                        # TODO: test
                        raise TypeError((
                            "class {c} overwrites attribute {a} of {b} with a value, "
                            "which is not a compatible {t}"
                        ).format(b=repr(base_class.__qualname__), c=repr(cls.__qualname__), a=repr(name),
                                 t=repr(type(base_value))))
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


class Tool(_BaseTool, metaclass=_ToolMeta):
    pass
