# SPDX-License-Identifier: LGPL-3.0-or-later
# dlb - a Pythonic build tool
# Copyright (C) 2020 Daniel Lutz <dlu-ch@users.noreply.github.com>

"""Utilities for dependency-aware tool execution.
This is an implementation detail - do not import it unless you know what you are doing."""

__all__ = ['ChunkProcessor', 'RedoContext', 'RunResult']

import hashlib
from typing import Any, Collection, Dict, List, Iterable, Mapping, Optional, Set, Tuple, Union

from .. import ut
from .. import di
from .. import fs
from .. import cf
from . import _error
from . import _rundb
from . import _worktree
from . import _context
from . import _depend
from . import input
from . import _dependaction


class ChunkProcessor:
    separator = b'\n'
    max_chunk_size = 2 ** 16  # asyncio.streams._DEFAULT_LIMIT

    def process(self, chunk: bytes, is_last: bool):
        raise NotImplementedError


class RedoContext(_context.ReadOnlyContext):

    # Do *not* construct RedoContext objects manually!
    # dlb.ex.Tool.start() will construct one and pass it as *context* to dlb.ex.Tool.redo(..., context).
    def __init__(self, context: _context.Context, dependency_action_by_path: Dict[fs.Path, _dependaction.Action]):
        if not isinstance(dependency_action_by_path, dict):
            raise TypeError

        # must be True for all values *v* of *dependency_action_by_path*:
        # isinstance(v.dependency, _depend.OutputDependency) and v.dependency.Value is dlb.fs.Path.

        super().__init__(context)
        self._dependency_action_by_path = dependency_action_by_path
        self._paths_of_modified = set(
            p for p, a in dependency_action_by_path.items()
            if not hasattr(a, 'treat_as_modified_after_redo') or a.treat_as_modified_after_redo())

    def prepare_arguments(self, arguments: Iterable[Any], *, cwd: Optional[fs.PathLike] = None) \
            -> Tuple[List[str], fs.Path]:
        cwd = fs.Path('.') if cwd is None else self.working_tree_path_of(cwd, is_dir=True, allow_temporary=True)

        longest_dotdot_prefix = ()
        str_arguments = []
        for a in arguments:
            if isinstance(a, fs.Path):
                if not a.is_absolute():
                    a = self.working_tree_path_of(a, existing=True,
                                                  allow_temporary=True).relative_to(cwd, collapsable=True)
                    c = a.components[1:]
                    if c[:len(longest_dotdot_prefix)] == longest_dotdot_prefix:
                        while len(longest_dotdot_prefix) < len(c) and c[len(longest_dotdot_prefix)] == '..':
                            longest_dotdot_prefix += ('..',)
                a = a.native
            str_arguments.append(str(a))

        if longest_dotdot_prefix:
            _worktree.normalize_dotdot_native_components(cwd.components[1:] + longest_dotdot_prefix,
                                                         ref_dir_path=str(self.root_path.native))
        return str_arguments, cwd

    def _prepare_for_subprocess(self, helper_file: fs.PathLike, arguments: Iterable[Any],
                                cwd: Optional[fs.PathLike], forced_env: Optional[Mapping[str, str]]) \
            -> Tuple[fs.Path, List[str], Dict[str, str], fs.Path]:

        if not isinstance(helper_file, fs.Path):
            helper_file = fs.Path(helper_file)

        if helper_file.is_dir():
            raise ValueError(f"cannot execute directory: {helper_file.as_string()!r}")

        helper_file_path = self.helper[helper_file]

        commandline_tokens, cwd = self.prepare_arguments(arguments, cwd=cwd)
        commandline_tokens.insert(0, str(helper_file_path.native))

        if forced_env is None:
            forced_env = {}
        env = {k: v for k, v in self.env.items()}
        env.update(forced_env)

        if di.is_unsuppressed_level(cf.level.helper_execution):
            argument_list_str = ', '.join([repr(t) for t in commandline_tokens[1:]])
            env_str = repr(env)
            msg = (
                f'execute helper {helper_file.as_string()!r}\n'
                f'    path: \t{helper_file_path.as_string()!r}\n'
                f'    arguments: \t{argument_list_str}\n'
                f'    directory: \t{cwd.as_string()!r}\n'
                f'    environment: \t{env_str}'
            )
            di.inform(msg, level=cf.level.helper_execution)

        # commandline_tokens is to be used by asyncio.create_subprocess_exec():
        #  - all elements must be str
        #  - must contain executable as first element

        return helper_file, commandline_tokens, env, cwd

    def _open_potential_file(self, potential_file: Union[Optional[bool], fs.PathLike]):
        if potential_file is None:
            potential_file = cf.execute_helper_inherits_files_by_default

        if potential_file is True:
            return

        if not potential_file:
            import asyncio
            return asyncio.subprocess.DEVNULL

        potential_file = fs.Path(potential_file)
        if not potential_file.is_absolute():
            potential_file = self.root_path / potential_file
        return open(potential_file.native, 'wb')

    @staticmethod
    def _close_potential_file(f):
        try:
            c = f.close
        except AttributeError:
            pass
        else:
            c()

    async def execute_helper(self, helper_file: fs.PathLike, arguments: Iterable[Any] = (), *,
                             cwd: Optional[fs.PathLike] = None, expected_returncodes: Collection[int] = frozenset([0]),
                             forced_env: Optional[Mapping[str, str]] = None,
                             stdout_output: Union[Optional[bool], fs.PathLike] = None,
                             stderr_output: Union[Optional[bool], fs.PathLike] = None) -> int:

        helper_file, commandline_tokens, env, cwd = \
             self._prepare_for_subprocess(helper_file, arguments, cwd, forced_env)

        import asyncio
        stdout_file = self._open_potential_file(stdout_output)
        stderr_file = self._open_potential_file(stderr_output)
        try:
            # io.BytesIO() cannot be used for *stdout* or *stderr* because file-like in the sense of
            # asyncio.create_subprocess_exec() means (as of Python 3.8): has a method fileno()
            proc = await asyncio.create_subprocess_exec(
                *commandline_tokens, cwd=(self.root_path / cwd).native, env=env,
                stdin=None, stdout=stdout_file, stderr=stderr_file)

            await proc.communicate()
        finally:
            self._close_potential_file(stderr_file)
            self._close_potential_file(stdout_file)

        returncode = proc.returncode
        if returncode not in expected_returncodes:
            msg = f"execution of {helper_file.as_string()!r} returned unexpected exit code {proc.returncode}"
            raise _error.HelperExecutionError(msg)

        return returncode

    async def execute_helper_with_output(
            self, helper_file: fs.PathLike, arguments: Iterable[Any] = (), *,
            cwd: Optional[fs.PathLike] = None, expected_returncodes: Collection[int] = frozenset([0]),
            forced_env: Optional[Dict[str, str]] = None,
            output_to_process: int = 1, other_output: Union[Optional[bool], fs.PathLike] = None,
            chunk_processor: Optional[ChunkProcessor] = None) -> Tuple[int, Any]:

        import asyncio

        if output_to_process not in (1, 2):
            raise ValueError(f"'output_to_process' must be 1 or 2")

        if chunk_processor is None:
            chunk_separator = None
            max_chunk_size = ChunkProcessor.max_chunk_size
        else:
            if not isinstance(chunk_processor, ChunkProcessor):
                msg = f"'chunk_processor' must be None or a ChunkProcessor object, not {type(chunk_processor)!r}"
                raise TypeError(msg)
            chunk_separator = chunk_processor.separator
            if not isinstance(chunk_separator, bytes):
                msg = f"'chunk_processor.separator' must be bytes object, not {type(chunk_separator)!r}"
                raise TypeError(msg)
            if not chunk_separator:
                msg = f"'chunk_processor.separator' must not be empty"
                raise ValueError(msg)
            max_chunk_size = max(1, int(chunk_processor.max_chunk_size))

        helper_file, commandline_tokens, env, cwd = \
            self._prepare_for_subprocess(helper_file, arguments, cwd, forced_env)

        other_file = self._open_potential_file(other_output)

        try:

            if output_to_process == 2:
                stdout = other_file
                stderr = asyncio.subprocess.PIPE
            else:
                stdout = asyncio.subprocess.PIPE
                stderr = other_file

            # from asyncio.subprocess.create_subprocess_exec() - cannot use create_subprocess_exec() because it does not
            # expose transport
            loop = asyncio.events.get_event_loop()
            protocol_factory = lambda: asyncio.subprocess.SubprocessStreamProtocol(limit=max_chunk_size, loop=loop)
            transport, protocol = await loop.subprocess_exec(
                protocol_factory, *commandline_tokens,
                stdin=None, stdout=stdout, stderr=stderr,
                cwd=(self.root_path / cwd).native, env=env)
            proc = asyncio.subprocess.Process(transport, protocol, loop)

            pipe = proc.stderr if output_to_process == 2 else proc.stdout
            # *pipe* is asyncio.StreamReader(limit=limit, ...) setup for file descriptor *output_to_process*

            if chunk_processor is None:
                stdout, stderr = await proc.communicate()
                output: bytes = stderr if output_to_process == 2 else stdout
            else:
                # read from pipe until EOF or error
                reached_eof = False

                try:
                    while True:
                        try:
                            chunk = await pipe.readuntil(chunk_separator)
                        except asyncio.IncompleteReadError as e:
                            chunk = e.partial  # EOF reached without *chunk_separator*
                            reached_eof = True

                        if not reached_eof:
                            chunk = chunk[:-len(chunk_separator)]
                        chunk_processor.process(chunk, reached_eof)

                        if reached_eof:
                            break  # pipe closed
                except:
                    # e.g. asyncio.LimitOverrunError:
                    # more than *max_chunk_size* bytes without *chunk_separator* since last *chunk_separator*,
                    # e.consumed bytes could be read with pipe.readexactly().

                    # properly read or close the pipe to avoid blocking of the executable
                    transport.close()
                    await proc.wait()
                    raise

                # then wait for subprocess to exit
                # dot not call before EOF was read from *pipe* to avoid unlimited memory consumption in case of error
                await proc.wait()
                output = chunk_processor.result

        finally:
            self._close_potential_file(other_file)

        returncode = proc.returncode
        if returncode not in expected_returncodes:
            msg = f"execution of {helper_file.as_string()!r} returned unexpected exit code {proc.returncode}"
            raise _error.HelperExecutionError(msg)

        return returncode, output

    # This is part of the (stable) public interface of dlb.ex.RedoContext but is undocumented on purpose.
    async def execute_helper_raw(self, helper_file: fs.PathLike, arguments: Iterable[Any] = (), *,
                                 cwd: Optional[fs.PathLike] = None, forced_env: Optional[Dict[str, str]] = None,
                                 stdin=None, stdout=None, stderr=None, limit: int = 2**16) \
            -> 'asyncio.subprocess.Process':

        helper_file, commandline_tokens, env, cwd = \
             self._prepare_for_subprocess(helper_file, arguments, cwd, forced_env)

        import asyncio
        return await asyncio.create_subprocess_exec(*commandline_tokens, cwd=(self.root_path / cwd).native, env=env,
                                                    stdin=stdin, stdout=stdout, stderr=stderr, limit=limit)

    def replace_output(self, path: fs.PathLike, source: fs.PathLike):
        # *path* may or may not exist.
        #
        # After if successful completion
        #  - *path* exists
        #  - *source* does not exist

        if not isinstance(path, fs.Path):
            path = fs.Path(path)
        if not isinstance(source, fs.Path):
            source = fs.Path(source)

        action = self._dependency_action_by_path.get(path)
        if action is None:
            msg = f"path is not contained in any explicit output dependency: {path.as_string()!r}"
            raise ValueError(msg)

        try:
            replacer = action.replace_filesystem_object
        except AttributeError:
            msg = f"do not know how to replace: {path.as_string()!r}"
            raise ValueError(msg) from None

        if path.is_dir() != source.is_dir():
            if path.is_dir():
                msg = f"cannot replace directory by non-directory: {path.as_string()!r}"
            else:
                msg = f"cannot replace non-directory by directory: {path.as_string()!r}"
            raise ValueError(msg)

        try:
            source = self.working_tree_path_of(source, allow_temporary=True)
        except _error.WorkingTreePathError as e:
            if e.oserror is not None:
                e = e.oserror
            msg = (
                f"'source' is not a permitted working tree path of an existing filesystem object: "
                f"{source.as_string()!r}\n"
                f"  | reason: {ut.exception_to_line(e)}"
            )
            raise ValueError(msg)

        if path == source:
            raise ValueError(f"cannot replace a path by itself: {path.as_string()!r}")

        did_replace = replacer(destination=path, source=source, context=self)
        if did_replace:
            self._paths_of_modified.add(path)

        return did_replace

    @property
    def modified_outputs(self) -> Set[fs.Path]:
        return self._paths_of_modified


class RunResult:
    # Attribute represent concrete dependencies of a tool instance.
    # Explicit dependencies are referred to the tool instance.
    # Non-explicit dependencies can be set exactly once, if *redo* is True.
    #
    # To be used by start() and redo().

    # Do *not* construct RunResult objects manually!
    # dlb.ex.Tool.start() will construct one and pass it as *result* to dlb.ex.Tool.redo(..., result, ...).
    def __init__(self, tool, redo: bool):
        super().__setattr__('_tool', tool)
        super().__setattr__('_redo', bool(redo))

    def complete(self):  # does not conflict with name of attribute of tool class (because single word)
        return self

    @property
    def iscomplete(self) -> bool:
        return True

    def __setattr__(self, key, value):
        if not self._redo:
            raise AttributeError

        try:
            role = getattr(self._tool.__class__, key)
            if not isinstance(role, _depend.Dependency):
                raise AttributeError
        except AttributeError:
            raise AttributeError(f"{key!r} is not a dependency")

        if key in self.__dict__:
            raise AttributeError(f"{key!r} is already assigned")

        if role.explicit:
            raise AttributeError(f"{key!r} is not a non-explicit dependency")

        if value is not None:
            validated_value = role.validate(value)
        elif not role.required:
            validated_value = None
        else:
            raise ValueError('value for required dependency must not be None')

        super().__setattr__(key, validated_value)

    def __getattr__(self, item):
        try:
            role = getattr(self._tool.__class__, item)
            if not isinstance(role, _depend.Dependency):
                raise AttributeError
        except AttributeError:
            raise AttributeError(f"{item!r} is not a dependency")

        if role.explicit:
            return getattr(self._tool, item)

        return NotImplemented

    def __bool__(self) -> bool:
        return self._redo

    def __repr__(self) -> str:
        # noinspection PyProtectedMember
        dependencies = [(n, getattr(self, n)) for n in self._tool.__class__._dependency_names]
        args = ', '.join('{}={}'.format(k, repr(v)) for k, v in dependencies if v is not NotImplemented)
        return f"{self.__class__.__name__}({args})"


def get_memo_for_fs_input_dependency_from_rundb(encoded_path: str, last_encoded_memo: Optional[bytes],
                                                needs_redo: bool, root_path: fs.Path) \
        -> Tuple[_rundb.FilesystemObjectMemo, bool]:

    path = None
    memo = _rundb.FilesystemObjectMemo()

    try:
        path = _rundb.decode_encoded_path(encoded_path)  # may raise ValueError
    except ValueError:
        if not needs_redo:
            di.inform(f"redo necessary because of invalid encoded path: {encoded_path!r}",
                      level=cf.level.redo_suspicious_reason)
            needs_redo = True

    if path is None:
        return memo, needs_redo

    try:
        # do _not_ check if in managed tree: does no harm if _not_ in managed tree
        # may raise OSError or ValueError (if 'path' not representable on native system)
        memo = _worktree.read_filesystem_object_memo(root_path / path)
    except (ValueError, FileNotFoundError):
        # ignore if did not exist according to valid 'encoded_memo'
        did_not_exist_before_last_redo = False
        try:
            did_not_exist_before_last_redo = \
                last_encoded_memo is None or _rundb.decode_encoded_fsobject_memo(last_encoded_memo).stat is None
        except ValueError:
            pass
        if not did_not_exist_before_last_redo:
            if not needs_redo:
                msg = f"redo necessary because of non-existent filesystem object: {path.as_string()!r}"
                di.inform(msg, level=cf.level.redo_reason)
                needs_redo = True
    except OSError:
        # comparision not possible -> redo
        if not needs_redo:
            msg = f"redo necessary because of inaccessible filesystem object: {path.as_string()!r}"
            di.inform(msg, level=cf.level.redo_reason)
            needs_redo = True  # comparision not possible -> redo

    return memo, needs_redo  # memo.state may be None


def check_and_memorize_explicit_fs_input_dependencies(tool, dependency_actions: Tuple[_dependaction.Action, ...],
                                                      context: _context.Context) \
        -> Dict[str, _rundb.FilesystemObjectMemo]:

    # For all explicit input dependencies of *tool* in *dependency_actions* for filesystem objects:
    # Check existence, read and check its FilesystemObjectMemo.
    #
    # Treats all definitions file of this tool class that are in the managed tree as explicit input dependencies.
    #
    # Returns a dictionary whose key are encoded managed tree paths and whose values are the corresponding
    # FilesystemObjectMemo m with ``m.stat is not None``.

    memo_by_encoded_path: Dict[str, _rundb.FilesystemObjectMemo] = {}

    for action in dependency_actions:
        # read memo of each filesystem object of a explicit input dependency in a repeatable order
        if action.dependency.explicit and isinstance(action.dependency, _depend.InputDependency) \
                and action.dependency.Value is fs.Path:
            validated_value_tuple = action.dependency.tuple_from_value(getattr(tool, action.name))
            for p in validated_value_tuple:  # p is a dlb.fs.Path
                try:
                    try:
                        p = context.working_tree_path_of(p, existing=True, collapsable=False)
                    except ValueError as e:
                        if isinstance(e, _error.WorkingTreePathError) and e.oserror is not None:
                            raise e.oserror
                        if not p.is_absolute():
                            raise ValueError('not a managed tree path') from None
                        # absolute paths to the management tree are ok

                    # p is a relative path of a filesystem object in the managed tree or an absolute path
                    # of filesystem object outside the managed tree
                    if not p.is_absolute():
                        encoded_path = _rundb.encode_path(p)
                        memo = memo_by_encoded_path.get(encoded_path)
                        if memo is None:
                            memo = _worktree.read_filesystem_object_memo(context.root_path / p)  # may raise OSError
                        action.check_filesystem_object_memo(memo)  # raise ValueError if memo is not as expected
                        memo_by_encoded_path[encoded_path] = memo
                        assert memo.stat is not None
                except ValueError as e:
                    msg = (
                        f"input dependency {action.name!r} contains an invalid path: {p.as_string()!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise _error.DependencyError(msg) from None
                except FileNotFoundError:
                    msg = (
                        f"input dependency {action.name!r} contains a path of a "
                        f"non-existent filesystem object: {p.as_string()!r}"
                    )
                    raise _error.DependencyError(msg) from None
                except OSError as e:
                    msg = (
                        f"input dependency {action.name!r} contains a path of an "
                        f"inaccessible filesystem object: {p.as_string()!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise _error.DependencyError(msg) from None

    return memo_by_encoded_path


def check_explicit_fs_output_dependencies(tool, dependency_actions: Tuple[_dependaction.Action, ...],
                                          encoded_paths_of_explicit_input_dependencies: Set[str],
                                          needs_redo: bool,
                                          context: _context.Context) \
        -> Tuple[Dict[fs.Path, _dependaction.Action], Set[fs.Path], bool]:
    # For all explicit output dependencies of *tool* in *dependency_actions* for filesystem objects:
    # Checks existence, reads and checks its FilesystemObjectMemo.
    #
    # Returns ``True`` if at least one of the filesystem objects does not exist.

    dependency_action_by_encoded_path = {}
    dependency_action_by_path = {}

    # managed tree paths of existing filesystem objects with unexpected memos (e.g. wrong type):
    obstructive_paths = set()

    for action in dependency_actions:

        # read memo of each filesystem object of a explicit input dependency in a repeatable order
        if action.dependency.explicit and isinstance(action.dependency, _depend.OutputDependency) and \
                action.dependency.Value is fs.Path:

            validated_value_tuple = action.dependency.tuple_from_value(getattr(tool, action.name))
            for p in validated_value_tuple:  # p is a dlb.fs.Path
                try:
                    p = context.working_tree_path_of(p, existing=True, collapsable=True)
                except ValueError as e:
                    msg = (
                        f"output dependency {action.name!r} contains a path that is not a managed tree path: "
                        f"{p.as_string()!r}\n"
                        f"  | reason: {ut.exception_to_line(e)}"
                    )
                    raise _error.DependencyError(msg) from None
                encoded_path = _rundb.encode_path(p)
                if encoded_path in encoded_paths_of_explicit_input_dependencies:
                    msg = (
                        f"output dependency {action.name!r} contains a path that is also an explicit "
                        f"input dependency: {p.as_string()!r}"
                    )
                    raise _error.DependencyError(msg)
                a = dependency_action_by_encoded_path.get(encoded_path)
                if a is not None:
                    msg = (
                        f"output dependencies {action.name!r} and {a.name!r} both contain the same path: "
                        f"{p.as_string()!r}"
                    )
                    raise _error.DependencyError(msg)
                dependency_action_by_encoded_path[encoded_path] = action
                dependency_action_by_path[p] = action
                memo = None
                try:
                    # may raise OSError or ValueError (if 'path' not representable on native system)
                    memo = _worktree.read_filesystem_object_memo(context.root_path / p)
                    action.check_filesystem_object_memo(memo)  # raise ValueError if memo is not as expected
                except (ValueError, OSError) as e:
                    if memo is not None and memo.stat is not None:
                        obstructive_paths.add(p)
                    if not needs_redo:
                        msg = (
                            f"redo necessary because of filesystem object: {p.as_string()!r}\n"
                            f"    reason: {ut.exception_to_line(e)}"
                        )
                        di.inform(msg, level=cf.level.redo_reason)
                        needs_redo = True

    return dependency_action_by_path, obstructive_paths, needs_redo


def check_envvar_dependencies(tool, dependency_actions: Tuple[_dependaction.Action, ...], context: _context.Context):
    envvar_value_by_name = {}
    action_by_envvar_name = {}

    for action in dependency_actions:
        d = action.dependency
        if d.Value is input.EnvVar.Value:
            a = action_by_envvar_name.get(d.name)
            if a is not None:
                msg = (
                    f"input dependencies {action.name!r} and {a.name!r} both define the same "
                    f"environment variable: {d.name!r}"
                )
                raise _error.DependencyError(msg)
            if action.dependency.explicit:
                for ev in action.dependency.tuple_from_value(getattr(tool, action.name)):
                    envvar_value_by_name[ev.name] = ev.raw  # ev is a _depend.EnvVarInput.Value
            else:
                value = envvar_value_by_name.get(d.name)
                if value is None:
                    if d.required:
                        try:
                            value = context.env[d.name]
                        except KeyError as e:
                            raise _error.RedoError(*e.args) from None
                    else:
                        value = context.env.get(d.name)
                if value is not None:
                    envvar_value_by_name[d.name] = value  # validate at redo
            action_by_envvar_name[d.name] = action

    envvar_digest = b''
    for name in sorted(envvar_value_by_name):
        envvar_digest += ut.to_permanent_local_bytes((name, envvar_value_by_name[name]))
    if len(envvar_digest) >= 20:
        envvar_digest = hashlib.sha1(envvar_digest).digest()

    return envvar_value_by_name, envvar_digest


ut.set_module_name_to_parent_by_name(vars(), __all__)
