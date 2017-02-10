__all__ = ['Context']

_contexts = []


class NestingError(Exception):
    pass


class Context:

    @staticmethod
    def current():
        return _contexts[-1] if _contexts else None

    def __enter__(self):
        _contexts.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not (_contexts and _contexts[-1] == self):
            raise NestingError
        _contexts.pop()
