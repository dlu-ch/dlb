__all__ = ('Tool', 'DefinitionAmbiguityError', 'DependencyRoleAssignmentError')

import sys
import re
import os
import typing
import inspect
from . import depend
from . import util
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


# key: (source_path, in_archive_path, lineno), value: class with metaclass _ToolMeta
_tool_class_by_definition_location = {}


class DefinitionAmbiguityError(SyntaxError):
    pass


class DependencyRoleAssignmentError(ValueError):
    pass


# noinspection PyProtectedMember,PyUnresolvedReferences
class _ToolBase:
    def __init__(self, **kwargs):
        super().__init__()

        # replace all dependency roles by concrete dependencies or None

        # order is important:
        dependency_names = self.__class__._dependency_names   # type: typing.Tuple[str, ...]
        names_of_assigned = set()
        for name, value in kwargs.items():
            if name not in dependency_names:
                names = ', '.join(repr(n) for n in dependency_names)
                msg = (
                    f"keyword argument does not name a dependency role of {self.__class__.__qualname__!r}: {name!r}\n"
                    f"  | dependency roles: {names}"
                )
                raise DependencyRoleAssignmentError(msg)

            role = getattr(self.__class__, name)
            if not role.explicit:
                msg = (
                    f"keyword argument does name a non-explicit dependency role: {name!r}\n"
                    f"  | non-explicit dependency must not be assigned at construction"
                )
                raise DependencyRoleAssignmentError(msg)

            if value is None:
                validated_value = None
                if role.required:
                    msg = f"keyword argument for required dependency role must not be None: {name!r}"
                    raise DependencyRoleAssignmentError(msg)
            else:
                validated_value = role.validate(value, None)

            object.__setattr__(self, name, validated_value)
            names_of_assigned.add(name)

        for name in sorted(set(dependency_names) - names_of_assigned):
            role = getattr(self.__class__, name)
            if role.required and role.explicit:
                msg = f"missing keyword argument for required and explicit dependency role: {name!r}"
                raise DependencyRoleAssignmentError(msg)
            object.__setattr__(self, name, None)

    # final
    def run(self):
        # TODO: implement, document
        raise NotImplementedError

    def __setattr__(self, name: str, value):
        raise AttributeError

    def __delattr__(self, name: str):
        raise AttributeError

    def __repr__(self):
        names = self.__class__._dependency_names
        args = ', '.join('{}={}'.format(n, repr(getattr(self, n))) for n in names)
        return f'{self.__class__.__qualname__}({args})'


# noinspection PyProtectedMember
depend._inject_into(_ToolBase, 'Tool', '.'.join(_ToolBase.__module__.split('.')[:-1]))


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
                f"  | make sure the matching module search path is an absolute path when the "
                f"defining module is imported"
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
            msg = (
                f"invalid tool definition: location of definition is unknown\n"
                f"  | class: {cls!r}\n"
                f"  | define the class in a regular file or in a zip archived with '.zip'\n"
                f"  | note also the importance of upper and lower case of module search paths on "
                f"case-insensitive filesystems"
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
                if not (isinstance(value, _ToolBase.Dependency) and isinstance(value, depend.ConcreteDependency)):
                    msg = (
                        f"the value of {name!r} must be an instance of a concrete subclass of "
                        f"'dlb.ex.Tool.Dependency'"
                    )
                    raise TypeError(msg)
                for base_class in cls.__bases__:
                    base_value = base_class.__dict__.get(name, None)
                    if base_value is not None and not value.compatible_and_no_less_restrictive(base_value):
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

    def _get_dependency_names(cls) -> typing.Tuple[str, ...]:
        dependencies = {n: getattr(cls, n) for n in dir(cls) if DEPENDENCY_NAME_REGEX.match(n)}
        pairs = [(-v.RANK, not v.required, n) for n, v in dependencies.items() if isinstance(v, depend.Dependency)]
        pairs.sort()
        # order: input - intermediate - output, required first
        return tuple(p[-1] for p in pairs)

    def __setattr__(cls, name, value):
        raise AttributeError

    def __delattr__(cls, name):
        raise AttributeError


class Tool(_ToolBase, metaclass=_ToolMeta):
    pass


# noinspection PyCallByClass
type.__setattr__(Tool, '__module__', '.'.join(_ToolBase.__module__.split('.')[:-1]))
util.set_module_name_to_parent_by_name(vars(), [n for n in __all__ if not 'Tool'])
