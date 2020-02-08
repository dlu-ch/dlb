import sys
assert sys.version_info >= (3, 6)
import os
import os.path
import pathlib
import stat
import time
import typing
import tempfile
import shutil
import sqlite3
import dlb.fs

__all__ = ['Context']

_contexts = []


class NestingError(Exception):
    pass


class NotRunningError(Exception):
    pass


class ManagementTreeError(Exception):
    pass


class NoWorkingTreeError(Exception):
    pass


class WorkingTreeTimeError(Exception):
    pass


# a directory containing a directory with this name is considered a working tree of dlb
_MANAGEMENTTREE_DIR_NAME = '.dlbroot'


# a directory containing a directory with this name is considered a working tree of dlb
_MTIME_PROBE_FILE_NAME = 'o'
assert _MTIME_PROBE_FILE_NAME.upper() != _MTIME_PROBE_FILE_NAME


_LOCK_DIRNAME = 'lock'


_MTIME_TEMPORARY_DIR_NAME = 't'


_RUNDB_FILE_NAME = 'runs.sqlite'


def exception_to_string(e):
    s = str(e)
    if s:
        return s
    return e.__class__.__qualname__


def remove_filesystem_object(path, ignore_non_existing=False):  # TODO implement safer version (see ???)
    try:
        try:
            os.remove(path)  # does remove symlink
        except IsADirectoryError:
            shutil.rmtree(path, ignore_errors=False)
    except FileNotFoundError:
        if not ignore_non_existing:
            raise


def _get_root():
    if not _contexts:
        raise NotRunningError
    return _contexts[0]


class _ContextMeta(type):
    def __getattribute__(self, name):
        refer = not name.startswith('_')
        try:
            a = super().__getattribute__(name)
            refer = refer and isinstance(a, property)
        except AttributeError:
            if not refer:
                raise
        if refer:
            a = getattr(_get_root(), name)  # delegate to root context
        return a

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise AttributeError("public attributes of 'dlb.ex.Context' are read-only")
        return super().__setattr__(key, value)


class _RootSpecifics:
    def __init__(self, path_cls):
        self._path_cls = path_cls

        # cwd must be a working tree`s root
        working_tree_path_str = os.path.abspath(os.getcwd())
        try:
            self._working_tree_path = path_cls(path_cls.Native(working_tree_path_str), is_dir=True)
            self._real_working_tree_path = pathlib.Path(os.path.realpath(working_tree_path_str))
                # TODO check if canonical-case path
            if not os.path.samefile(working_tree_path_str, str(self._working_tree_path.native)):
                msg = (
                    f'current directory probably violates imposed path restrictions: {working_tree_path_str!r}\n'
                    f'  | reason: path cannot be checked due to a dlb bug or a moved directory'
                )
                raise ValueError(msg)
            working_tree_path_str = str(self._working_tree_path.native)
        except (ValueError, OSError) as e:
            msg = (  # assume that exception_to_string(e) include the working_tree_path
                f'current directory violates imposed path restrictions\n'
                f'  | reason: {exception_to_string(e)}\n'
                f'  | move the working directory or choose a less restrictive path class for the root context'
            )
            raise ValueError(msg) from None

        self._is_working_tree_case_sensitive = True
        self._mtime_probe = None
        self._rundb_connection = None

        management_tree_path = self._working_tree_path  / (_MANAGEMENTTREE_DIR_NAME + '/')

        # 1. is this a working tree?

        msg = (
            f'current directory is no working tree: {working_tree_path_str!r}\n'
            f'  | reason: does not contain a directory {_MANAGEMENTTREE_DIR_NAME!r} that is not a symbolic link'
        )
        try:
            mode = os.lstat(management_tree_path.native).st_mode
        except Exception:
            raise NoWorkingTreeError(msg) from None
        if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
            raise NoWorkingTreeError(msg) from None

        # 2. if yes: lock it

        lock_dir_path_str = str((management_tree_path / (_LOCK_DIRNAME + '/')).native)
        try:
            try:
                mode = os.lstat(lock_dir_path_str).st_mode
                if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
                    remove_filesystem_object(lock_dir_path_str)
            except FileNotFoundError:
                pass
            os.mkdir(lock_dir_path_str)
        except OSError as e:
            msg = (
                f'cannot aquire lock for exclusive access to working tree {working_tree_path_str!r}\n'
                f'  | reason: {exception_to_string(e)}\n'
                f'  | to break the lock (if you are sure no other dlb process is running): remove {lock_dir_path_str!r}'
            )
            raise ManagementTreeError(msg)

        # 3. then prepare it

        try:  # OSError in this block -> ManagementTreeError
            try:
                # prepare o for mtime probing
                mtime_probe_path_str = str((management_tree_path / _MTIME_PROBE_FILE_NAME).native)
                mtime_probeu_path_str = str((management_tree_path / _MTIME_PROBE_FILE_NAME.upper()).native)
                remove_filesystem_object(mtime_probe_path_str, ignore_non_existing=True)
                remove_filesystem_object(mtime_probeu_path_str, ignore_non_existing=True)

                self._mtime_probe = open(mtime_probe_path_str, 'xb')  # always a fresh file (no link to an existing one)
                probe_stat = os.lstat(mtime_probe_path_str)
                try:
                    probeu_stat = os.lstat(mtime_probeu_path_str)
                except FileNotFoundError:
                    pass
                else:
                    self._is_working_tree_case_sensitive = not os.path.samestat(probe_stat, probeu_stat)

                temporary_path_str = str((management_tree_path / _MTIME_TEMPORARY_DIR_NAME).native)
                remove_filesystem_object(temporary_path_str, ignore_non_existing=True)
                os.mkdir(temporary_path_str)

                rundb_path_str = str((management_tree_path / _RUNDB_FILE_NAME).native)
                self._rundb_connection = self._open_or_create_rundb(rundb_path_str)
            except Exception:
                self.close_and_unlock_if_open()
                raise
        except (OSError, sqlite3.Error) as e:
            msg = (
                f'failed to setup management tree for {working_tree_path_str!r}\n'
                f'  | reason: {exception_to_string(e)}'
            )
            raise ManagementTreeError(msg) from None

    @property
    def root_path(self) -> dlb.fs.Path:
        return self._working_tree_path

    def create_temporary(self, suffix='', prefix='t', is_dir=False) -> dlb.fs.Path:
        if not isinstance(suffix, str) or not isinstance(prefix, str):
            raise TypeError("'prefix' and 'suffix' must be str")
        if not prefix:
            raise ValueError("'prefix' must not be empty")
        if os.path.sep in prefix or (os.path.altsep and os.path.altsep in prefix):
            raise ValueError("'prefix' must not contain a path separator")
        if os.path.sep in suffix or (os.path.altsep and os.path.altsep in suffix):
            raise ValueError("'prefix' must not contain a path separator")

        t = (self._working_tree_path / (_MANAGEMENTTREE_DIR_NAME + '/' + _MTIME_TEMPORARY_DIR_NAME + '/')).native
        is_dir = bool(is_dir)
        if is_dir:
            p_str = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=t)
        else:
            fd, p_str = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=t)
        try:
            p = self._path_cls(p_str, is_dir=is_dir)
        except ValueError as e:
            msg = (
                f'path violates imposed path restrictions\n'
                f'  | reason: {exception_to_string(e)}\n'
                f"  | check specified 'prefix' and 'suffix'"
            )
            raise ValueError(msg) from None
        return p

    @property
    def working_tree_time_ns(self) -> int:
        self._mtime_probe.seek(0)
        self._mtime_probe.write(b'0')  # updates mtime
        return os.fstat(self._mtime_probe.fileno()).st_mtime_ns

    def get_managed_tree_path(self, path: typing.Union[str, dlb.fs.Path]) -> dlb.fs.Path:
        is_dir = None
        if isinstance(path, str):
            native_path = pathlib.Path(path)  # path may be ''
            seps = (os.path.sep, os.path.altsep)
            if path[-1:] in seps or (path[-1:] == '.' and path[-2:-1] in seps) or \
                    not native_path.parts or native_path.parts[-1:]  == ('..',):
                is_dir = True
        elif isinstance(path, dlb.fs.Path):
            is_dir = path.is_dir()
            native_path = path.native.raw
        else:
            raise TypeError("'path' must be 'str' or 'dlb.fs.Path'")

        if not os.path.isabs(native_path):
            native_path = os.path.join(self._real_working_tree_path, native_path)
        native_path = pathlib.Path(os.path.realpath(native_path))
        sr = os.lstat(native_path)
        try:
            rel_path = native_path.relative_to(self._real_working_tree_path)
            if rel_path.parts[:1] in (('..',), (_MANAGEMENTTREE_DIR_NAME,)):
                raise ValueError
        except ValueError:
            raise ValueError(f'path not in managed tree: {native_path!r}') from None

        mtp = self._path_cls(self._path_cls.Native(rel_path), is_dir=stat.S_ISDIR(sr.st_mode))
        if is_dir is not None and is_dir != mtp.is_dir():
            raise ValueError(f"form of 'path' does not match the type of filesystem object: {str(mtp.native)!r}")

        return mtp

    def _open_or_create_rundb(self, rundb_path):
        try:
            mode = os.lstat(rundb_path).st_mode
            if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                remove_filesystem_object(rundb_path)
        except FileNotFoundError:
            pass

        connection = sqlite3.connect(rundb_path, isolation_level='DEFERRED')  # raises sqlite3.Error on error
        return connection

    def _cleanup(self):
        self._rundb_connection.commit()
        temporary_path = self._working_tree_path / (_MANAGEMENTTREE_DIR_NAME + '/' + _MTIME_TEMPORARY_DIR_NAME + '/')
        remove_filesystem_object(temporary_path.native, ignore_non_existing=True)

    def _cleanup_and_delay_to_working_tree_time_change(self):
        t0 = time.time()  # time_ns() not in Python 3.6
        wt0 = self.working_tree_time_ns
        self._cleanup()  # seize the the day
        while True:
            wt = self.working_tree_time_ns
            if wt != wt0:  # guarantee G-T2
                break
            if time.time() - t0 > 10.0:  # at most 10 for s
                msg = (
                    'working tree time did not change for at least 10 s of system time\n'
                    '  | was the system time adjusted in this moment?'
                )
                raise WorkingTreeTimeError(msg)
            time.sleep(0.015)  # typical effective working tree time resolution: 10 ms

    def close_and_unlock_if_open(self):  # safe to call multiple times
        # called while self is not an active context (note: an exception may already have happened)
        most_serious_exception = None

        if self._mtime_probe:
            try:
                self._mtime_probe.close()
            except Exception as e:
                most_serious_exception = e
            self._mtime_probe = None

        if self._rundb_connection:
            try:
                self._rundb_connection.close()  # note: uncommitted changes are lost!
            except Exception as e:
                most_serious_exception = e
            self._rundb_connection = None

        lock_dir_path = self._working_tree_path / (_MANAGEMENTTREE_DIR_NAME + '/' + _LOCK_DIRNAME + '/')
        try:
            os.rmdir(lock_dir_path.native)  # unlock
        except Exception:
            pass

        if most_serious_exception:
            raise most_serious_exception

    def cleanup_and_close(self):  # "normal" exit of root context (as far as it is special for root context)
        first_exception = None

        try:
             self._cleanup_and_delay_to_working_tree_time_change()
        except Exception as e:
             first_exception = e

        try:
            self.close_and_unlock_if_open()
        except Exception as e:
             first_exception = e

        if first_exception:
            if isinstance(first_exception, (OSError, sqlite3.Error)):
                msg = (
                    f'failed to cleanup management tree for {str(self._working_tree_path.native)!r}\n'
                    f'  | reason: {exception_to_string(first_exception)}'
                )
                raise ManagementTreeError(msg) from None
            else:
                raise first_exception


class Context(metaclass=_ContextMeta):

    def __init__(self, path_cls=dlb.fs.Path):
        if not (isinstance(path_cls, type) and issubclass(path_cls, dlb.fs.Path)):
            raise TypeError("'path_cls' is not a subclass of 'dlb.fs.Path'")
        self._path_cls = path_cls
        self._root_specifics = None

    @property
    def root(self):
        return _get_root()

    @property
    def active(self):
        if not _contexts:
            raise NotRunningError
        return _contexts[-1]

    @property
    def path_cls(self) -> dlb.fs.Path:
        return self._path_cls

    def __getattr__(self, name):
        try:
            if name.startswith('_'):
                raise AttributeError
            return getattr(_get_root()._root_specifics, name)  # delegate to _RootSpecifics
        except AttributeError:
            raise AttributeError(f'{self.__class__.__qualname__!r} object has no attribute {name!r}') from None

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise AttributeError("public attributes of 'dlb.ex.Context' instances are read-only")
        return super().__setattr__(key, value)

    def __enter__(self):
        if _contexts:
            try:
                self._path_cls(self.root_path)
            except ValueError as e:
                msg = (  # assume that exception_to_string(e) include the working_tree_path
                    f"working tree's root path violates path restrictions imposed by this context\n"
                    f'  | reason: {exception_to_string(e)}\n'
                    f'  | move the working directory or choose a less restrictive path class for the root context'
                )
                raise ValueError(msg) from None
        else:
            self._root_specifics = _RootSpecifics(self._path_cls)
        _contexts.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not (_contexts and _contexts[-1] == self):
            raise NestingError
        _contexts.pop()
        if self._root_specifics:
            self._root_specifics.cleanup_and_close()
            self._root_specifics = None
