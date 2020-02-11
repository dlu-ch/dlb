import typing
import dlb.ex.mult


class Dependency(dlb.ex.mult.MultiplicityHolder):
    # Each instance d represents a dependency role.
    # The return value of d.validate() is a concrete dependency, if d.multiplicity is None and
    # a tuple of concrete dependencies otherwise.

    def __init__(self, required=True):
        super().__init__()

    # overwrite in base classes
    def validate_element(self, value, context: typing.Optional[dlb.ex.Context]) -> typing.Hashable:
        msg = (
            f"{self.__class__!r} is abstract\n"
            f"  | use one of its documented subclasses instead"
        )
        raise NotImplementedError(msg)

    # final
    def validate(self, value, context) -> typing.Union[typing.Hashable, typing.Tuple[typing.Hashable, ...]]:
        m = self.multiplicity

        if m is None:
            return self.validate_element(value, context)

        if m is not None and isinstance(value, (bytes, str)):  # avoid iterator over characters by mistake
            raise TypeError('since dependency has a multiplicity, value must be iterable (other than string or bytes)')

        values = tuple(self.validate_element(e, context) for e in value)
        n = len(values)
        if n not in m:
            raise ValueError(f'value has {n} members, which is not accepted according to the specified multiplicity {m}')
        return values  # tuple
