# SPDX-License-Identifier: GPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

import sys
import collections
import typing
import platform
import marshal
from . import context
from . import tool as tool_
from .. import fs
from .. import version
assert sys.version_info >= (3, 6)


PLATFORM_ID = marshal.dumps((platform.platform(), sys.hexversion, version.__version__))

ToolInfo = collections.namedtuple('ToolInfo', ('permanent_local_id', 'definition_paths'))

# key: dlb.ex.Tool, value: ToolInfo
_registered_info_by_tool = {}


def _get_and_register_tool_identity(tool: typing.Type[tool_.Tool]) -> typing.Tuple[bytes, fs.Path]:
    # Return a ToolIdentity with a permanent local id of tool and the managed tree path of the defining source file,
    # if it is in the managed tree.

    definition_path_in_managed_tree = None

    # noinspection PyUnresolvedReferences
    definition_path, in_archive_path, lineno = tool.definition_location

    try:
        definition_path_in_managed_tree = context.Context.get_managed_tree_path(definition_path)
        definition_path = definition_path_in_managed_tree.as_string()
        if definition_path.startswith('./'):
            definition_path = definition_path[2:]
    except ValueError:
        pass

    permanent_local_id = marshal.dumps((definition_path, in_archive_path, lineno))
    return permanent_local_id, definition_path_in_managed_tree


def get_and_register_tool_info(tool: typing.Type[tool_.Tool]) -> ToolInfo:
    # Return a ToolInfo with a permanent local id of tool and a set of all source file in the managed tree in
    # which the class or one of its baseclass of type `base_cls` is defined.
    #
    # The result is cached.
    #
    # The permanent local id is the same on every Python run as long as PLATFORM_ID remains the same
    # (at least that's the idea).
    # Note however, that the behaviour of tools not only depends on their own code but also on all imported
    # objects. So, its up to the programmer of the tool, how much variability a tool with a unchanged
    # permanent local id can show.

    if not issubclass(tool, tool_.Tool):
        raise TypeError("'tool' must be a 'dlb.ex.Tool'")

    info = _registered_info_by_tool.get(tool)
    if info is not None:
        return info

    # collect the managed tree paths of tool and its base classes that are tools

    definition_paths = set()
    for c in reversed(tool.mro()):
        if c is not tool and issubclass(c, tool_.Tool):
            base_info = get_and_register_tool_info(c)
            definition_paths = definition_paths.union(base_info.definition_paths)

    permanent_local_id, definition_path = _get_and_register_tool_identity(tool)
    if definition_path is not None:
        definition_paths.add(definition_path)

    info = ToolInfo(permanent_local_id=permanent_local_id, definition_paths=definition_paths)
    _registered_info_by_tool[tool] = info

    return info
