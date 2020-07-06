from abc import ABC
from abc import abstractmethod
from collections.abc import MutableMapping
import functools


def store(cls):
    class _store_wrapper(cls, MutableMapping):
        def __init__(self, *args, **kwargs):
            super().__init__(self, *args, **kwargs)
            self._deleted = set()
            functools.update_wrapper(self, cls)
        def __delitem__(self, key):
            super().__delitem__(key)
            self._deleted.add(key)
        def __getitem__(self, key):
            if key in self._deleted:
                raise KeyError('{} has been deleted'.format(key))
            return super().__getitem__(key)
        def __setitem__(self, key, value):
            if key in self._deleted:
                raise KeyError('{} has been deleted'.format(key))
            if key in self:
                raise KeyError('{} already set'.format(key))
            return super().__setitem__(key, value)
    return _store_wrapper


@store
class Memory(dict):
    pass
