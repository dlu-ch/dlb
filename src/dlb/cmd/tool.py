import re

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
    RANK = 0

    def __init__(self, is_required=True):
        self._is_required = is_required

    @property
    def is_required(self):
        return self._is_required

    @property
    def obj(self):
        raise NotImplementedError

    def is_superset_of(self, other):
        return isinstance(other, self.__class__)

    def validate(self, value):
        return value


class _OutputDependency(_Dependency):
    RANK = 1


class _IntermediateDependency(_Dependency):
    RANK = 2


class _InputDependency(_Dependency):
    RANK = 3


class _RegularInputFileDependency(_InputDependency):
    pass


class _InputDirectoryDependency(_InputDependency):
    pass


class _RegularOutputFileDependency(_OutputDependency):
    pass


class _OutputDirectoryDependency(_OutputDependency):
    pass


class _BaseTool:

    Dependency = _Dependency
    Dependency.__qualname__ = 'Tool.Dependency'

    Input = _InputDependency
    Input.__qualname__ = 'Tool.Input'

    Input.RegularFile = _RegularInputFileDependency
    Input.RegularFile.__qualname__ = Input.__qualname__ + '.RegularFile'
    Input.Directory = _InputDirectoryDependency
    Input.Directory.__qualname__ = Input.__qualname__ + '.Directory'

    Output = _OutputDependency
    Output.__qualname__ = 'Tool.Output'

    Output.RegularFile = _RegularOutputFileDependency
    Output.RegularFile.__qualname__ = Output.__qualname__ + '.RegularFile'
    Output.Directory = _OutputDirectoryDependency
    Output.Directory.__qualname__ = Output.__qualname__ + '.Directory'

    Intermediate = _IntermediateDependency
    Intermediate.__qualname__ = 'Tool.Intermediate'

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


class _ToolMeta(type):

    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)

        for attrib in ['__new__', '__init__', '__setattr__', '__delattr__']:
            if attrib in cls.__dict__:
                raise AttributeError("must not be overwritten in a 'dlb.cmd.Tool': {}".format(repr(attrib)))

        cls.check_own_attributes()
        # TODO: prevent conflicting attributes in base classes

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
                if not isinstance(value, _Dependency):
                    raise TypeError("the value of {} must be a 'dlb.cmd.Tool.Dependency'".format(repr(name)))
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not base_value.is_superset_of(value):
                        # TODO: test
                        raise TypeError(
                            "class {c} overwrites attribute {a} of {b} with a value, which is not a compatible {t}".format(
                                b=repr(base_class.__qualname__), c=repr(cls.__qualname__), a=repr(name),
                                t=repr(type(base_value))))
            else:
                raise AttributeError((
                    "invalid class attribute name: {} "
                    "(every class attribute of a 'dlb.cmd.Tool' must be named "
                    "like 'UPPER_CASE_WORD' or 'lower_case_word)").format(repr(name)))

    def _get_dependency_names(cls):
        # TODO: test with non-Tool base classes
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
