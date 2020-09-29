from ..errors import CopyError
from .store import Store
from .store import StoreDriver


class Memory(Store):
    """ In-Memory Store

    A store implementation that lives in process memory. Memory stores cannot
    be copied or pickled as they are not meant to leave the host process. This
    may make them incompatible with multiprocessing drivers.
    """
    def __init__(self):
        self._driver = type('MemoryDriver', (dict, StoreDriver), {})()

    @property
    def driver(self):
        return self._driver

    def __truediv__(self, other):
        """
        Store.__truediv__ relies on copying, which is disallowed for memory
        stores.
        """
        new_instance = Memory.__new__(Memory)
        new_instance._driver = self._driver
        new_instance._namespace = (*self._namespace, other)
        return new_instance

    def __copy__(self):
        raise CopyError('Cannot copy in-memory store')

    def __deepcopy__(self, memo):
        raise self.__copy__()

    def __getstate__(self):
        raise CopyError('Cannot transport in-memory store')

    def __setstate__(self, state):
        raise CopyError('Cannot transport in-memory store')
