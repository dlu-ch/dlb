import dlb.fs

__all__ = ['Context']

_contexts = []


class NestingError(Exception):
    pass

class NoneActive(Exception):
    pass


class _ContextMeta(type):
    @property
    def root(self):
        if not _contexts:
            raise NoneActive
        return _contexts[0]

    @property
    def active(self):
        if not _contexts:
            raise NoneActive
        return _contexts[-1]


class Context(metaclass=_ContextMeta):

    # a directory containing a directory with this name is considered a working tree of dlb
    MANAGINGTREE_DIR_NAME = '.dlbroot'

    def __init__(self, path_cls=dlb.fs.Path):
        if not (isinstance(path_cls, type) and issubclass(path_cls, dlb.fs.Path)):
            raise TypeError("'path_cls' is not a subclass of 'dlb.fs.Path'")

        self._path_cls = path_cls
        self._working_tree_root_path = NotImplemented  # only root context defines it

    @property
    def root_path(self):
        return self.root._working_tree_root_path

    def _create_temporary(self):  # ???
        pass

    def _remove_temporary(self):   # ???
        pass

    def _create_mtime_probe_file(self):  # ???
        pass

    def _open_rundb_exclusively(self):  # ???
        pass

    def _close_rundb(self):  # ???
        pass

    def _prepare_root(self):
        # called before self while self is not yet an active context

        self._open_rundb_exclusively()  # serves as lock for all dlb processes

        self._remove_temporary()
        self._create_temporary()
        self._create_mtime_probe_file()

    # ???
    def _cleanup_root(self):
        # called while self is not an active context anymore (note: an exception may already have happend)
        try:
            self._remove_temporary()
        except:
            pass
        self._close_rundb()

    def __enter__(self):
        if not _contexts:
            self._prepare_root()
        _contexts.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not (_contexts and _contexts[-1] == self):
            raise NestingError
        _contexts.pop()
        if not _contexts:
            self._cleanup_root()
