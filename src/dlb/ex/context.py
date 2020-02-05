import os
import os.path
import stat
import shutil
import dlb.fs

__all__ = ['Context']

_contexts = []


class NestingError(Exception):
    pass


class NoneActiveError(Exception):
    pass


class ManagementTreeError(Exception):
    pass


class NoWorkingTree(Exception):
    pass


# a directory containing a directory with this name is considered a working tree of dlb
_MANAGEMENTTREE_DIR_NAME = '.dlbroot'


# a directory containing a directory with this name is considered a working tree of dlb
_MTIME_PROBE_FILE_NAME = 'o'
assert _MTIME_PROBE_FILE_NAME.upper() != _MTIME_PROBE_FILE_NAME


_MTIME_TEMPORARY_DIRNAME = 't'


_RUNDB_FILE_NAME = 'runs.sqlite'


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
            raise NoneActiveError
        return _contexts[0]

    @property
    def active(self):
        if not _contexts:
            raise NoneActiveError
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

        management_tree_path = os.path.join(self._working_tree_path, _MANAGEMENTTREE_DIR_NAME)

        msg = (
            f'current directory is no working tree: {self._working_tree_path!r}\n'
            f'  | a working tree must contain a directory {_MANAGEMENTTREE_DIR_NAME!r} that is not a symbolic link'
        )
        try:
            mode = os.lstat(management_tree_path).st_mode
        except FileNotFoundError:
            raise NoWorkingTree(msg) from None
        if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
            raise NoWorkingTree(msg) from None

        rundb_path = os.path.join(management_tree_path, _RUNDB_FILE_NAME)
        self._rundb = self._open_or_create_rundb_exclusively(rundb_path)  # serves as lock for all dlb processes

        try:
            # prepare o for mtime probing
            mtime_probe_path = os.path.join(management_tree_path, _MTIME_PROBE_FILE_NAME)
            mtime_probeu_path = os.path.join(management_tree_path, _MTIME_PROBE_FILE_NAME.upper())
            try:
                remove_filesystem_object(mtime_probe_path, ignore_non_existing=True)
                remove_filesystem_object(mtime_probeu_path, ignore_non_existing=True)
            except OSError as e:
                msg = (
                    f'cannot prepare management tree: {e}'
                    f'  | permissions ok?'
                )
                raise ManagementTreeError(msg) from None

            self._mtime_probe = open(mtime_probe_path, 'xb')
            probe_stat = os.lstat(mtime_probe_path)
            try:
                probeu_stat = os.lstat(mtime_probeu_path)
            except FileNotFoundError:
                pass
            else:
                self._is_working_tree_case_sensitive = not os.path.samestat(probe_stat, probeu_stat)

            remove_filesystem_object(self.temporary_path, ignore_non_existing=True)
            os.mkdir(self.temporary_path)
        except Exception:
            self.close()
            raise

    @property
    def root_path(self):
        return self._working_tree_path

    @property
    def temporary_path(self):
        return os.path.join(self._working_tree_path, _MANAGEMENTTREE_DIR_NAME, _MTIME_TEMPORARY_DIRNAME)

    @property
    def working_tree_time_ns(self):
        self._mtime_probe.seek(0)
        self._mtime_probe.write(b'0')  # updates mtime
        return os.fstat(self._mtime_probe.fileno()).st_mtime_ns

    def _open_or_create_rundb_exclusively(self, rundb_path):  # ???
        return None

    def _close_rundb(self):  # ???
        pass

    def close(self):  # safe to call multiple times
        # called while self is not an active context (note: an exception may already have happened)
        if self._mtime_probe:
            self._mtime_probe.close()
            self._mtime_probe = None
        try:
            remove_filesystem_object(self.temporary_path, ignore_non_existing=True)
        except:
            pass
        self._close_rundb()  # also: release lock


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
            self._root_specifics.close()
            self._root_specifics = None
