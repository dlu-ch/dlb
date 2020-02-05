import os
import os.path
import stat
import time
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


class _ContextMeta(type):
    @property
    def root(self):
        if not _contexts:
            raise NotRunningError
        return _contexts[0]

    @property
    def active(self):
        if not _contexts:
            raise NotRunningError
        return _contexts[-1]

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError
        a = getattr(self.root, name)  # delegate to root context
        return a

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise AttributeError("public attributes of 'dlb.ex.Context' are read-only")
        return super().__setattr__(key, value)


class _RootSpecifics:
    def __init__(self):
        # cwd must be a working tree`s root
        self._working_tree_path = os.path.abspath(os.getcwd())
        self._is_working_tree_case_sensitive = True
        self._mtime_probe = None
        self._rundb_connection = None

        management_tree_path = os.path.join(self._working_tree_path, _MANAGEMENTTREE_DIR_NAME)

        # 1. is this a working tree?

        msg = (
            f'current directory is no working tree: {self._working_tree_path!r}\n'
            f'  | a working tree must contain a directory {_MANAGEMENTTREE_DIR_NAME!r} that is not a symbolic link'
        )
        try:
            mode = os.lstat(management_tree_path).st_mode
        except Exception:
            raise NoWorkingTreeError(msg) from None
        if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
            raise NoWorkingTreeError(msg) from None

        # 2. if yes: lock it

        lock_dir_path = os.path.join(management_tree_path, _LOCK_DIRNAME)
        try:
            try:
                mode = os.lstat(lock_dir_path).st_mode
                if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
                    remove_filesystem_object(lock_dir_path)
            except FileNotFoundError:
                pass
            os.mkdir(lock_dir_path)
        except OSError as e:
            msg = (
                f'cannot aquire lock for exclusive access to working tree {self._working_tree_path!r}\n'
                f'  | reason: {exception_to_string(e)}\n'
                f'  | to break the lock (if you are sure, no other dlb process is running): remove {lock_dir_path!r}'
            )
            raise ManagementTreeError(msg)

        # 3. then prepare it

        try:  # OSError in this block -> ManagementTreeError
            try:
                # prepare o for mtime probing
                mtime_probe_path = os.path.join(management_tree_path, _MTIME_PROBE_FILE_NAME)
                mtime_probeu_path = os.path.join(management_tree_path, _MTIME_PROBE_FILE_NAME.upper())
                remove_filesystem_object(mtime_probe_path, ignore_non_existing=True)
                remove_filesystem_object(mtime_probeu_path, ignore_non_existing=True)

                self._mtime_probe = open(mtime_probe_path, 'xb')  # always a fresh file (no link to an existing one)
                probe_stat = os.lstat(mtime_probe_path)
                try:
                    probeu_stat = os.lstat(mtime_probeu_path)
                except FileNotFoundError:
                    pass
                else:
                    self._is_working_tree_case_sensitive = not os.path.samestat(probe_stat, probeu_stat)

                remove_filesystem_object(self.temporary_path, ignore_non_existing=True)
                os.mkdir(self.temporary_path)

                rundb_path = os.path.join(management_tree_path, _RUNDB_FILE_NAME)
                self._rundb_connection = self._open_or_create_rundb(rundb_path)
            except Exception:
                self.close_and_unlock_if_open()
                raise
        except (OSError, sqlite3.Error) as e:
            msg = (
                f'failed to setup management tree for {self._working_tree_path!r}\n'
                f'  | reason: {exception_to_string(e)}'
            )
            raise ManagementTreeError(msg) from None

    @property
    def root_path(self):
        return self._working_tree_path

    @property
    def temporary_path(self):
        return os.path.join(self._working_tree_path, _MANAGEMENTTREE_DIR_NAME, _MTIME_TEMPORARY_DIR_NAME)

    @property
    def working_tree_time_ns(self):
        self._mtime_probe.seek(0)
        self._mtime_probe.write(b'0')  # updates mtime
        return os.fstat(self._mtime_probe.fileno()).st_mtime_ns

    def _open_or_create_rundb(self, rundb_path):
        try:
            mode = os.lstat(rundb_path).st_mode
            if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                remove_filesystem_object(rundb_path)
        except FileNotFoundError:
            pass

        connection = sqlite3.connect(rundb_path, isolation_level='DEFERRED')  # raises sqlite3.Error on error
        return connection

    def _delay_to_working_tree_time_change(self):
        t0 = time.time()  # time_ns() not in Python 3.6
        wt0 = self.working_tree_time_ns
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

        try:
            remove_filesystem_object(self.temporary_path, ignore_non_existing=True)
        except Exception as e:
            most_serious_exception = e

        if self._mtime_probe:
            try:
                self._mtime_probe.close()
            except Exception as e:
                most_serious_exception = e
            self._mtime_probe = None

        if self._rundb_connection:
            try:
                # note: uncommitted changes are lost!
                self._rundb_connection.close()
            except Exception as e:
                most_serious_exception = e
            self._rundb_connection = None

        assert self._working_tree_path  # besser safe than sorry
        lock_dir_path = os.path.join(self._working_tree_path, _MANAGEMENTTREE_DIR_NAME, _LOCK_DIRNAME)
        try:
            os.rmdir(lock_dir_path)  # unlock
        except Exception:
            pass

        if most_serious_exception:
            raise most_serious_exception

    def cleanup_and_close(self):  # "normal" exit of root context (as far as it is special for root context)
        first_exception = None

        try:
             self._delay_to_working_tree_time_change()
        except Exception as e:
             first_exception = e

        try:
            self.close_and_unlock_if_open()
        except Exception as e:
             first_exception = e

        if first_exception:
            if isinstance(first_exception, (OSError, sqlite3.Error)):
                msg = (
                    f'failed to cleanup management tree for {self._working_tree_path!r}\n'
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

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError
        a = getattr(self.__class__.root._root_specifics, name)  # delegate to _RootSpecifics
        return a

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            raise AttributeError("public attributes of 'dlb.ex.Context' instances are read-only")
        return super().__setattr__(key, value)

    def __enter__(self):
        if not _contexts:
            self._root_specifics = _RootSpecifics()
        _contexts.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not (_contexts and _contexts[-1] == self):
            raise NestingError
        _contexts.pop()
        if self._root_specifics:
            self._root_specifics.cleanup_and_close()
            self._root_specifics = None
