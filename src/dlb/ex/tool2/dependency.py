import re
import typing
import dlb.ex.mult
import dlb.ex.context


class Dependency(dlb.ex.mult.MultiplicityHolder):
    # Each instance d represents a dependency role.
    # The return value of d.validate() is a concrete dependency, if d.multiplicity is None and
    # a tuple of concrete dependencies otherwise.

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

    # overwrite in base classes
    def validate_single(self, value, context: typing.Optional[dlb.ex.Context]) -> typing.Hashable:
        if value is None:
            raise TypeError("'value' must not be None")
        return value

    # final
    def validate(self, value, context) -> typing.Union[typing.Hashable, typing.Tuple[typing.Hashable, ...]]:
        if self.__class__.validate_single is Dependency.validate_single:
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
            if self._unique and v in values:
                raise ValueError(f'sequence of dependencies must be duplicate-free, but contains {v!r} more than once')
            values.append(v)

        n = len(values)
        if n not in m:
            msg = f'value has {n} members, which is not accepted according to the specified multiplicity {m}'
            raise ValueError(msg)

        return tuple(values)


class Input(Dependency):
    pass


class Intermediate(Dependency):
    pass


class Output(Dependency):
    pass


class _FilesystemObjectMixin:
    def __init__(self, cls=dlb.fs.Path, **kwargs):
        super().__init__(**kwargs)
        if not (isinstance(cls, type) and issubclass(cls, dlb.fs.Path)):
            raise TypeError("'cls' is not a subclass of 'dlb.fs.Path'")
        self._path_cls = cls

    @property
    def cls(self) -> dlb.fs.Path:
        return self._path_cls

    def validate_single(self, value, context: typing.Optional[dlb.ex.Context]) -> dlb.fs.Path:
        value = super().validate_single(value, context)
        return self._path_cls(value)


class _FilesystemObjectInputMixin:
    def __init__(self, ignore_permission=True, **kwargs):
        super().__init__(**kwargs)
        self._ignore_permission = bool(ignore_permission)

    @property
    def ignore_permission(self) -> bool:
        return self._ignore_permission


class _NonDirectoryMixin(_FilesystemObjectMixin):
    def validate_single(self, value, context: typing.Optional[dlb.ex.Context]) -> dlb.fs.Path:
        value = super().validate_single(value, context)
        if value.is_dir():
            raise ValueError(f'directory path not valid for non-directory dependency: {value!r}')
        return value


class _DirectoryMixin(_FilesystemObjectMixin):
    def validate_single(self, value, context: typing.Optional[dlb.ex.Context]) -> dlb.fs.Path:
        value = super().validate_single(value, context)
        if not value.is_dir():
            raise ValueError(f'non-directory path not valid for directory dependency: {value!r}')
        return value


class RegularFileInput(_NonDirectoryMixin, _FilesystemObjectInputMixin, Input):
    pass


class NonRegularFileInput(_NonDirectoryMixin, _FilesystemObjectInputMixin, Input):
    pass


class DirectoryInput(_DirectoryMixin, _FilesystemObjectInputMixin, Input):
    pass


class RegularFileOutput(_NonDirectoryMixin, Output):
    pass


class NonRegularFileOutput(_NonDirectoryMixin, Output):
    pass


class DirectoryOutput(_DirectoryMixin, Output):
    pass


class EnvVarInput(Input):

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

    def validate_single(self, value, context: typing.Optional[dlb.ex.Context]) -> typing.Union[str, typing.Dict[str, str]]:
        # value is the name of an environment variable

        value = str(super().validate_single(value, None))

        if not isinstance(value, str):
            raise TypeError("'value' must be a str")
        if not value:
            raise ValueError("'value' must not be empty")

        if not isinstance(context, dlb.ex.Context):
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
