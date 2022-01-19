from ..errors import CopyError
from .store import Store
from .store import TagDB


class Memory(Store):
    """ In-Memory Store

    A store implementation that lives in process memory. Memory stores cannot
    be copied or pickled as they are not meant to leave the host process. This
    may make them incompatible with multiprocessing drivers.
    """

    class MemoryTagDB(TagDB):
        """
        Memory Stores don't persist state, so these methods can be ignored
        """

        def refresh(self):
            pass

        def checkpoint(self):
            pass

        def dump(self, name):
            pass

    def __init__(self):
        self._store = {}
        self._tagdb = self.MemoryTagDB(self)

    def __contains__(self, callnode):
        return callnode in self._store

    def _load_value(self, callnode):
        value = self._store[callnode]
        return value

    def from_sha256(self, sha256):
        for key in self._store.keys():
            if key.sha256() == sha256:
                return key
        raise KeyError(f'KeyError: {str(sha256)}')

    def store(self, callnode, value, **tags):
        self._store[callnode] = value
        self._tagdb.update(callnode, tags)

    def remove(self, callnode):
        del self._store[callnode]
        self._tagdb.remove(callnode)

    def _load_tags(self, callnode):
        return self._tagdb.tags(callnode)

    def filter(self, *tag_conditions):
        return self._tagdb.query(*tag_conditions)

    def __copy__(self):
        raise CopyError('Cannot copy in-memory store')

    def __deepcopy__(self, memo):
        raise self.__copy__()

    def __getstate__(self):
        raise CopyError('Cannot transport in-memory store')

    def __setstate__(self, state):
        raise CopyError('Cannot transport in-memory store')
