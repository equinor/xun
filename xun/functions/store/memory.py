from ..errors import CopyError
from .store import Store


class Memory(Store):
    """ In-Memory Store

    A store implementation that lives in process memory. Memory stores cannot
    be copied or pickled as they are not meant to leave the host process. This
    may make them incompatible with multiprocessing drivers.
    """

    def __init__(self):
        self._container = {}

    def __contains__(self, callnode):
        return callnode in self._container

    def _load_value(self, callnode):
        value = self._container[callnode]
        return value

    def remove(self, callnode):
        del self._store[callnode]
    def _store(self, callnode, value, **tags):
        self._container[callnode] = value

    def _load_tags(self, callnode):
        raise NotImplementedError

    def filter(self, *tag_conditions):
        raise NotImplementedError

    def __copy__(self):
        raise CopyError('Cannot copy in-memory store')

    def __deepcopy__(self, memo):
        raise self.__copy__()

    def __getstate__(self):
        raise CopyError('Cannot transport in-memory store')

    def __setstate__(self, state):
        raise CopyError('Cannot transport in-memory store')
