import sys
import re
import collections
import os
import typing
import inspect
import dlb.fs
assert sys.version_info >= (3, 6)


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

__all__ = [
    'Tool',
    'PropagatedEnvVar'
]


PropagatedEnvVar = collections.namedtuple('PropagatedEnvVar', ['name', 'value'])

#: key: (cls_id, (start, stop, step)), value: mult_class
_classes_with_multiplicity = {}

# key: (source_path, in_archive_path, lineno), value: class with metaclass _ToolMeta
_tool_class_by_definition_location = {}


class DefinitionAmbiguityError(SyntaxError):
    pass


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

        if stop is not None and start < stop <= start + step:  # is start the only member?
            stop = start + 1
            step = 1
        if stop == start:
            start = 0
            stop = 1

        assert start >= 0
        assert stop is None or stop > start
        assert step > 0

        m = (start, stop, step)
        k = (id(cls), m)

        # noinspection PyPep8Naming
        MultipleDependency = _classes_with_multiplicity.get(k)

        if MultipleDependency is None:
            bases = []
            for c in cls.__mro__:
                if _DependencyRole in c.__bases__:
                    bases.append(c)

            class MultipleDependency(_MultipleDependencyRoleBase, *bases):
                _member_role_class = cls
                _multiplicity = slice(*m)

        _classes_with_multiplicity[k] = MultipleDependency

        if stop is not None and stop == start + 1:
            suffix = str(start)
        else:
            suffix = (str(start) if start else '') + ':' + (str(stop) if stop is not None else '')
            if step > 1:
                suffix += ':' + str(step)
        suffix = f'[{suffix}]'

        MultipleDependency.__name__ = cls.__name__ + suffix
        MultipleDependency.__qualname__ = cls.__qualname__ + suffix

        return MultipleDependency


# list this as last class before abstract dependency role class in base class list
class _ConcreteDependencyMixin(metaclass=_ConcreteDependencyMixinMeta):
    #: None or slice.
    #: if slice: Exactly every multiplicity which is contained in this slice is valid (step must not be non-positive)
    _multiplicity = None

    def __init__(self, required=True):
        self._required = required

    @property
    def required(self):
        return self._required

    @property
    def multiplicity(self):
        return self.__class__.multiplicity

    def is_more_restrictive_than(self, other):
        return (
            isinstance(self, other.__class__)
            and not (other.required and not self.required)
            and (self.__class__.multiplicity is None) == (other.__class__.multiplicity is None)
        )

    @classmethod
    def _check_multiplicity(cls, n):
        m = cls.multiplicity
        if m is None:
            if n is not None:
                raise ValueError('dependency role has no multiplicity')
        else:
            if n < m.start:
                raise ValueError(f'value has {n} members, but minimum multiplicity is {m.start}')
            if m.stop is not None and n >= m.stop:
                raise ValueError(f'value has {n} members, but maximum multiplicity is {m.stop-1}')
            if (n - m.start) % m.step != 0:
                msg = f'value has {n} members, but multiplicity must be an integer multiple of {m.step} above {m.start}'
                raise ValueError(msg)

    @classmethod
    def is_multiplicity_valid(cls, n):
        if not (n is None or isinstance(n, int)):
            raise TypeError('multiplicity must be None or integer')
        try:
            cls._check_multiplicity(n)
        except ValueError:
            return False
        return True

    def initial(self):
        return NotImplemented

    def validate(self, value):
        # do _not_ call super().validate() here!
        if self.required and value is None:
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
            raise ValueError(f'non-directory path not valid for directory dependency: {value!r}')
        return value


class _NonDirectoryDependencyMixin(_PathDependencyMixin):
    def validate(self, value):
        value = super().validate(value)
        if value is not None and value.is_dir():
            raise ValueError(f'directory path not valid for non-directory dependency: {value!r}')
        return value


class _DependencyRole:
    #: Rank for ordering (the higher the rank, the earlier the dependency is needed)
    _RANK = 0


# noinspection PyAbstractClass
class _InputDependencyRole(_DependencyRole):
    _RANK = 3


# noinspection PyAbstractClass
class _IntermediateDependencyRole(_DependencyRole):
    _RANK = 2


# noinspection PyAbstractClass
class _OutputDependencyRole(_DependencyRole):
    _RANK = 1


class _MultipleDependencyRoleBase(_ConcreteDependencyMixin, _DependencyRole):
    #: Subclass of _Dependency for each member
    _member_role_class = None

    def __init__(self, required=True, unique=False, **kwargs):
        super().__init__(required=required)
        self._unique = unique
        # noinspection PyCallingNonCallable
        self._member_role_prototype = self.__class__._member_role_class(required=True, **kwargs)

    def validate(self, value):
        value = super().validate(value)

        if self.__class__.multiplicity is not None and isinstance(value, str):  # for safety
            raise TypeError('since dependency role has a multiplicity, value must be iterable (other than string)')
        value = tuple(self._member_role_prototype.validate(v) for v in value)

        self.__class__._check_multiplicity(len(value))

        if self._unique:
            prefix = []
            for v in value:
                if v in prefix:
                    raise ValueError(f'dependency must be duplicate-free, but contains {v!r} more than once')
                prefix.append(v)

        return value

    def is_more_restrictive_than(self, other):
        # only compare if multiplicity os None or not
        return (
            super().is_more_restrictive_than(other)
            and self._member_role_prototype.is_more_restrictive_than(other._member_role_prototype)
        )


class _RegularInputFileDependency(_NonDirectoryDependencyMixin, _ConcreteDependencyMixin, _InputDependencyRole):
    pass


class _InputDirectoryDependency(_DirectoryDependencyMixin, _ConcreteDependencyMixin, _InputDependencyRole):
    pass


class _InputEnvVarDependency(_ConcreteDependencyMixin, _InputDependencyRole):

    def __init__(self, name, validator=None, propagate=False, **kwargs):
        super().__init__(**kwargs)

        if not (isinstance(name, str) and str):
            raise TypeError("'var_name' must be a non-empty string")

        if validator is None:
            validator = '.*'
        if isinstance(validator, str):
            validator = re.compile(validator)
        elif isinstance(validator, type(re.compile(''))):
            pass
        elif callable(validator):
            pass
        else:
            raise TypeError("'validator' must be None, string, compiled regular expressed or callable")

        self._name = name

        self._validator = validator
        self._propagate = propagate

    def validate(self, value):
        validated_value = super().validate(value)

        if validated_value is not None:
            if callable(self._validator):
                validated_value = self._validator(validated_value)
            else:
                m = self._validator.fullmatch(validated_value)
                if not m:
                    raise ValueError(f'value does not match validator regular expression: {validated_value!r}')

                # return only validates/possibly modify value
                groups = m.groupdict()
                if groups:
                    # of all named groups: pick the group with the "smallest" name
                    validated_value = groups[sorted(groups)[0]]
                else:
                    # of all unnamed groups: pick the first one
                    groups = m.groups()
                    if groups:
                        validated_value = groups[0]

        if self._propagate:
            # propagate name and unchanged value
            value = PropagatedEnvVar(name=self._name, value=value)
        else:
            value = validated_value

        return value

    def initial(self):
        return os.environ.get(self._name)


class _RegularOutputFileDependency(_NonDirectoryDependencyMixin, _ConcreteDependencyMixin, _OutputDependencyRole):
    pass


class _OutputDirectoryDependency(_DirectoryDependencyMixin, _ConcreteDependencyMixin, _OutputDependencyRole):
    pass


# noinspection PyProtectedMember,PyUnresolvedReferences
class _ToolBase:
    def __init__(self, **kwargs):
        super().__init__()

        dependency_names = self.__class__._dependency_names

        # assign initial dependency to all dependency roles which provide one
        dependency_names_to_assign = set()
        for name in dependency_names:
            role = getattr(self.__class__, name)
            dependency = role.initial()
            if dependency is NotImplemented:
                dependency_names_to_assign.add(name)
            else:
                object.__setattr__(self, name, role.validate(dependency))

        names_of_assigned = set()
        for name, value in kwargs.items():
            if name not in dependency_names_to_assign:
                if name in dependency_names:
                    msg = (
                        f'dependency role {name!r} with automatic initialization must not be '
                        f'initialized by keyword parameter'
                    )
                    raise TypeError(msg)
                else:
                    names = ', '.join(repr(n) for n in dependency_names)
                    raise TypeError(f'{name!r} is not a dependency role of {self.__class__.__qualname__!r}: {names}')
            role = getattr(self.__class__, name)
            object.__setattr__(self, name, role.validate(value))
            names_of_assigned.add(name)

        for name in sorted(set(dependency_names_to_assign) - names_of_assigned):
            role = getattr(self.__class__, name)
            if role.required:
                raise TypeError(f'missing keyword parameter for required dependency role: {name!r}')
            object.__setattr__(self, name, None)

    def run(self):
        # TODO: implement, document
        raise NotImplementedError

    def __setattr__(self, name, value):
        raise AttributeError

    def __delattr__(self, name):
        raise AttributeError

    def __repr__(self):
        names = self.__class__._dependency_names
        args = ', '.join('{}={}'.format(n, repr(getattr(self, n))) for n in names)
        return f'{self.__class__.__qualname__}({args})'


def _inject_nested_class_into(owner, cls, name, owner_qualname=None):
    setattr(owner, name, cls)
    cls.__name__ = name
    if owner_qualname is None:
        owner_qualname = owner.__qualname__
    cls.__qualname__ = owner_qualname + '.' + name

# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase, _DependencyRole, 'DependencyRole', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase, _InputDependencyRole, 'Input', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase, _OutputDependencyRole, 'Output', 'Tool')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase, _IntermediateDependencyRole, 'Intermediate', 'Tool')

# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Input, _RegularInputFileDependency, 'RegularFile')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Input, _InputDirectoryDependency, 'Directory')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Input, _InputEnvVarDependency, 'EnvVar')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Output, _RegularOutputFileDependency, 'RegularFile')
# noinspection PyTypeChecker
_inject_nested_class_into(_ToolBase.Output, _OutputDirectoryDependency, 'Directory')

del _inject_nested_class_into


class _ToolMeta(type):
    def __init__(cls, name, bases, nmspc):
        super().__init__(name, bases, nmspc)

        # prevent attributes of _ToolBase from being overridden
        protected_attrs = (set(_ToolBase.__dict__.keys()) - {'__doc__', '__module__'} | {'__new__'})
        attrs = set(cls.__dict__) & protected_attrs
        if attrs:
            raise AttributeError("must not be overridden in a 'dlb.ex.Tool': {}".format(repr(sorted(attrs)[0])))

        cls.check_own_attributes()
        super().__setattr__('_dependency_names', cls._get_dependency_names())
        location = cls._find_definition_location(inspect.stack(context=0)[1])
        super().__setattr__('definition_location', location)
        _tool_class_by_definition_location[location] = cls

    def _find_definition_location(cls, defining_frame) -> typing.Tuple[str, typing.Optional[str], int]:
        # Return the location, cls is defined.
        # Raises DefinitionAmbiguityError, if the location is unknown or already a class with the same metaclass
        # was defined at the same location (realpath of an existing source file and line number).
        # If the source file is a zip archive with a filename ending in '.zip', the path relative to the root
        # of the archive is also given.

        # frame relies based on best practises, correct information not guaranteed
        source_lineno = defining_frame.lineno
        if not os.path.isabs(defining_frame.filename):
            msg = (
                f"invalid tool definition: location of definition depends on current working directory\n"
                f"  | class: {cls!r}\n"
                f"  | source file: {defining_frame.filename!r}\n"
                f"  | make sure the matching module search path is an absolute path when the defining module is imported"
            )
            raise DefinitionAmbiguityError(msg)

        source_path = os.path.realpath(defining_frame.filename)
        try:
            in_archive_path = None
            if not os.path.isfile(source_path):
                # zipimport:
                #     https://www.python.org/dev/peps/pep-0273/:
                #         "only files *.py and *.py[co] are available for import"
                #
                #     The source file path of an object imported from a zip archive has the relative path inside the
                #     archive appended to the path of the zip file (e.g. 'x.zip/y/z.py').
                #     A module name must be a Python identifier, so it must not contain a '.'.
                #     Therefore, the file path of the archive can always be determined unambiguously if the
                #     archive's filename contains a '.'.
                dir_path = os.path.dirname(source_path)

                ext = '.zip'
                i = dir_path.rfind(ext + os.path.sep)
                if i <= 0:
                    raise ValueError
                source_path, in_archive_path = dir_path[:i + len(ext)], source_path[i + len(ext) + 1:]

                if not os.path.isfile(source_path):
                    raise ValueError
                in_archive_path = os.path.normpath(in_archive_path)

        except Exception:
            raise
            msg = (
                f"invalid tool definition: location of definition is unknown\n"
                f"  | class: {cls!r}\n"
                f"  | define the class in a regular file or in a zip archived with '.zip'\n"
                f"  | note also the importance of upper and lower case of module search paths on case-insensitive filesystems"
            )
            raise DefinitionAmbiguityError(msg) from None

        location = source_path, in_archive_path, source_lineno
        existing_location = _tool_class_by_definition_location.get(location)
        if existing_location is not None:
            msg = (
                f"invalid tool definition: another 'Tool' class was defined on the same source file line\n"
                f"  | location: {source_path!r}:{source_lineno}\n"
                f"  | class: {existing_location!r}"
            )
            raise DefinitionAmbiguityError(msg)

        return location

    def check_own_attributes(cls):
        for name, value in cls.__dict__.items():
            if RESERVED_NAME_REGEX.match(name):
                pass
            elif EXECUTION_PARAMETER_NAME_REGEX.match(name):
                # if overridden: must be instance of type of overridden attribute
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not isinstance(value, type(base_value)):
                        msg = (
                            f"attribute {name!r} of base class may only be overridden with a value "
                            f"which is a {type(base_value)!r}"
                        )
                        raise TypeError(msg)
            elif DEPENDENCY_NAME_REGEX.match(name):
                if not (isinstance(value, _ToolBase.DependencyRole) and isinstance(value, _ConcreteDependencyMixin)):
                    msg = (
                        f"the value of {name!r} must be an instance of a concrete subclass of "
                        f"'dlb.ex.Tool.DependencyRole'"
                    )
                    raise TypeError(msg)
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not value.is_more_restrictive_than(base_value):
                        msg = (
                            f"attribute {name!r} of base class may only be overridden by "
                            f"a {type(base_value)!r} at least as restrictive"
                        )
                        raise TypeError(msg)
            else:
                msg = (
                    f"invalid class attribute name: {name!r} "
                    f"(every class attribute of a 'dlb.ex.Tool' must be named "
                    f"like 'UPPER_CASE_WORD' or 'lower_case_word)"
                )
                raise AttributeError(msg)

    def _get_dependency_names(cls):
        dependencies = {n: getattr(cls, n) for n in dir(cls) if DEPENDENCY_NAME_REGEX.match(n)}
        pairs = [(-v._RANK, not v.required, n) for n, v in dependencies.items() if isinstance(v, _DependencyRole)]
        pairs.sort()
        # order: input - intermediate - output, required first
        return tuple(p[-1] for p in pairs)

    def __setattr__(cls, name, value):
        raise AttributeError

    def __delattr__(cls, name):
        raise AttributeError


class Tool(_ToolBase, metaclass=_ToolMeta):
    pass
