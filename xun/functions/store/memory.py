from ..errors import CopyError
from .store import Store


class Memory(Store):
    """ In-Memory Store

    A store implementation that lives in process memory. Memory stores cannot
    be copied or pickled as they are not meant to leave the host process. This
    may make them incompatible with multiprocessing drivers.
    """
    def __init__(self):
        self._store = {}

    def __contains__(self, key):
        return key in self._store

    def load(self, key):
        return self._store[key]

    def metadata(self, key):
        return NotImplementedError

    def store(self, key, value, **metadata):
        self._store[key] = value

    def __copy__(self):
        raise CopyError('Cannot copy in-memory store')

    def __deepcopy__(self, memo):
        raise self.__copy__()

    def __getstate__(self):
        raise CopyError('Cannot transport in-memory store')

    def __setstate__(self, state):
        raise CopyError('Cannot transport in-memory store')
