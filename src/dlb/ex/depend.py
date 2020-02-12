import re
import typing
from . import mult
from . import context as context_
from .. import fs


# noinspection PyUnresolvedReferences
class Dependency(mult.MultiplicityHolder):
    # Each instance d represents a dependency role.
    # The return value of d.validate() is a concrete dependency, if d.multiplicity is None and
    # a tuple of concrete dependencies otherwise.

    #: Rank for ordering (the higher the rank, the earlier the dependency is needed)
    RANK = 0  # type: int

    def __init__(self, required=True, explicit=True, unique=True):
        super().__init__()
        self._required = bool(required)  # not checked by validate(), only for the caller
        self._explicit = bool(explicit)  # not checked by validate(), only for the caller
        self._unique = bool(unique)

    @property
    def required(self) -> bool:
        return self._required

    @property
    def explicit(self) -> bool:
        return self._explicit

    @property
    def unique(self) -> bool:
        return self._unique

    def compatible_and_no_less_restrictive(self, other) -> bool:
        if not isinstance(self, other.__class__):
            return False

        if (self.multiplicity is None) != (other.multiplicity is None):
            return False
        if self.multiplicity is not None:
            ss = self.multiplicity.as_slice
            so = other.multiplicity.as_slice
            if ss.step != so.step or ss.start < so.start or ss.stop > so.stop:
                return False

        if other.unique and not self.unique:
            return False
        if other.required and not self.required:
            return False
        if self.explicit != other.explicit:
            return False

        return True

    # overwrite in base classes
    def validate_single(self, value, context: typing.Optional[context_.Context]) -> typing.Hashable:
        if value is None:
            raise TypeError("'value' must not be None")
        return value

    # final
    def validate(self, value, context) -> typing.Union[typing.Hashable, typing.Tuple[typing.Hashable, ...]]:
        if not isinstance(self, ConcreteDependency):
            msg = (
                f"{self.__class__!r} is abstract\n"
                f"  | use one of its documented subclasses instead"
            )
            raise NotImplementedError(msg)

        m = self.multiplicity

        if m is None:
            return self.validate_single(value, context)

        if m is not None and isinstance(value, (bytes, str)):  # avoid iterator over characters by mistake
            raise TypeError("since dependency has a multiplicity, value must be iterable (other than 'str' or 'bytes')")

        values = []
        for v in value:
            v = self.validate_single(v, context)
            if self.unique and v in values:
                raise ValueError(f'sequence of dependencies must be duplicate-free, but contains {v!r} more than once')
            values.append(v)

        n = len(values)
        if n not in m:
            msg = f'value has {n} members, which is not accepted according to the specified multiplicity {m}'
            raise ValueError(msg)

        return tuple(values)


class ConcreteDependency:
    pass


class Input(Dependency):
    RANK = 3  # type: int


class Intermediate(Dependency):
    RANK = 2  # type: int


class Output(Dependency):
    RANK = 1  # type: int


class _FilesystemObjectMixin:
    def __init__(self, cls=fs.Path, **kwargs):
        super().__init__(**kwargs)
        if not (isinstance(cls, type) and issubclass(cls, fs.Path)):
            raise TypeError("'cls' is not a subclass of 'dlb.fs.Path'")
        self._path_cls = cls

    @property
    def cls(self) -> typing.Type[fs.Path]:
        return self._path_cls

    def compatible_and_no_less_restrictive(self, other) -> bool:
        if not super().compatible_and_no_less_restrictive(other):
            return False

        return issubclass(self.cls, other.cls)

    def validate_single(self, value, context: typing.Optional[context_.Context]) -> fs.Path:
        value = super().validate_single(value, context)
        return self._path_cls(value)


class _FilesystemObjectInputMixin:
    def __init__(self, ignore_permission=True, **kwargs):
        super().__init__(**kwargs)
        self._ignore_permission = bool(ignore_permission)

    @property
    def ignore_permission(self) -> bool:
        return self._ignore_permission

    def compatible_and_no_less_restrictive(self, other) -> bool:
        if not super().compatible_and_no_less_restrictive(other):
            return False

        if not other.ignore_permission and self.ignore_permission:
            return False

        return True


class _NonDirectoryMixin(_FilesystemObjectMixin):
    def validate_single(self, value, context: typing.Optional[context_.Context]) -> fs.Path:
        value = super().validate_single(value, context)
        if value.is_dir():
            raise ValueError(f'directory path not valid for non-directory dependency: {value!r}')
        return value


class _DirectoryMixin(_FilesystemObjectMixin):
    def validate_single(self, value, context: typing.Optional[context_.Context]) -> fs.Path:
        value = super().validate_single(value, context)
        if not value.is_dir():
            raise ValueError(f'non-directory path not valid for directory dependency: {value!r}')
        return value


class RegularFileInput(_NonDirectoryMixin, _FilesystemObjectInputMixin, ConcreteDependency, Input):
    pass


class NonRegularFileInput(_NonDirectoryMixin, _FilesystemObjectInputMixin, ConcreteDependency, Input):
    pass


class DirectoryInput(_DirectoryMixin, _FilesystemObjectInputMixin, ConcreteDependency, Input):
    pass


class RegularFileOutput(_NonDirectoryMixin, ConcreteDependency, Output):
    pass


class NonRegularFileOutput(_NonDirectoryMixin, ConcreteDependency, Output):
    pass


class DirectoryOutput(_DirectoryMixin, ConcreteDependency, Output):
    pass


class EnvVarInput(ConcreteDependency, Input):

    def __init__(self, restriction, example, **kwargs):
        super().__init__(**kwargs)

        if isinstance(restriction, str):
            restriction = re.compile(restriction)
        if not isinstance(restriction, typing.Pattern):
            raise TypeError("'restriction' must be regular expression (compiled or str)")
        if not isinstance(example, str):
            raise TypeError("'example' must be a str")

        if not restriction.fullmatch(example):
            raise ValueError(f"'example' is invalid with respect to 'restriction': {example!r}")

        self._restriction = restriction  # type: typing.Pattern
        self._example = example

    @property
    def restriction(self):
        return self._restriction

    @property
    def example(self):
        return self._example

    def compatible_and_no_less_restrictive(self, other) -> bool:
        if not super().compatible_and_no_less_restrictive(other):
            return False

        return self.restriction == other.restriction  # ignore example

    def validate_single(self, value, context: typing.Optional[context_.Context]) \
            -> typing.Union[str, typing.Dict[str, str]]:
        # value is the name of an environment variable

        value = str(super().validate_single(value, None))

        if not isinstance(value, str):
            raise TypeError("'value' must be a str")
        if not value:
            raise ValueError("'value' must not be empty")

        if not isinstance(context, context_.Context):
            raise TypeError("needs context")

        try:
            envvar_value = context.env[value]
        except KeyError as e:
            raise ValueError(*e.args)

        m = self._restriction.fullmatch(envvar_value)
        if not m:
            msg = f"value of environment variable {value!r} is invalid with respect to restriction: {envvar_value!r}"
            raise ValueError(msg)

        # return only validates/possibly modify value
        groups = m.groupdict()
        if groups:
            return groups

        return envvar_value


def _inject_into(owner, owner_name, owner_module):
    def _inject_nested_class_into(parent, cls, name, owner_qualname=None):
        setattr(parent, name, cls)
        cls.__module__ = owner_module
        cls.__name__ = name
        if owner_qualname is None:
            owner_qualname = parent.__qualname__
        cls.__qualname__ = owner_qualname + '.' + name

    _inject_nested_class_into(owner, Dependency, 'Dependency', owner_name)

    _inject_nested_class_into(owner, Input, 'Input', owner_name)
    _inject_nested_class_into(owner, Output, 'Output', owner_name)
    _inject_nested_class_into(owner, Intermediate, 'Intermediate', owner_name)

    _inject_nested_class_into(owner.Input, RegularFileInput, 'RegularFile')
    _inject_nested_class_into(owner.Input, NonRegularFileInput, 'NonRegularFile')
    _inject_nested_class_into(owner.Input, DirectoryInput, 'Directory')
    _inject_nested_class_into(owner.Input, EnvVarInput, 'EnvVar')

    _inject_nested_class_into(owner.Output, RegularFileOutput, 'RegularFile')
    _inject_nested_class_into(owner.Output, NonRegularFileOutput, 'NonRegularFile')
    _inject_nested_class_into(owner.Output, DirectoryOutput, 'Directory')
