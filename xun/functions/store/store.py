from ...memoized import memoized
from ..functions import CopyError
from abc import ABCMeta
from collections.abc import MutableMapping
import copyreg
import diskcache
import functools
import pickle


class StoreMeta(ABCMeta):
    """StoreMeta

    Metaclass for stores. Adds immutability and permanent deletion. Any class
    using this as metaclass will have to satisfy the interface of
    `collections.abc.MutableMapping`.

    Subject to change

    """
    def __new__(cls, name, bases, attrib_dict):
        bases += (MutableMapping,)

        if '__init__' in attrib_dict:
            init = attrib_dict['__init__']
            def __init__(self, *args, **kwargs):
                init(self, *args, **kwargs)
                self._store_deleted = set()
            attrib_dict['__init__'] = __init__

        if '__delitem__' in attrib_dict:
            delitem = attrib_dict['__delitem__']
            def __delitem__(self, key):
                delitem(self, key)
                self._store_deleted.add(key)
            attrib_dict['__delitem__'] = __delitem__

        if '__getitem__' in attrib_dict:
            getitem = attrib_dict['__getitem__']
            def __getitem__(self, key):
                if key in self._store_deleted:
                    raise KeyError('{} has been deleted'.format(key))
                return getitem(self, key)
            attrib_dict['__getitem__'] = __getitem__

        if '__setitem__' in attrib_dict:
            setitem = attrib_dict['__setitem__']
            def __setitem__(self, key, value):
                if key in self._store_deleted:
                    raise KeyError('{} has been deleted'.format(key))
                if key in self:
                    raise KeyError('{} already set'.format(key))
                setitem(self, key, value)
            attrib_dict['__setitem__'] = __setitem__

        return type.__new__(cls, name, bases, attrib_dict)


class Memory(metaclass=StoreMeta):
    def __init__(self):
        super().__init__()
        self.id = id(self)
        self.dict = Memory.get_dict(self.id)

    @staticmethod
    @memoized
    def get_dict(id):
        return dict()

    def __copy__(self):
        raise CopyError('Cannot copy memory store')

    def __deepcopy__(self, memo):
        raise CopyError('Cannot copy memory store')

    def __getstate__(self):
        return (self._store_deleted, self.id)

    def __setstate__(self, state):
        self._store_deleted = state[0]
        self.id = state[1]
        self.dict = Memory.get_dict(self.id)

    def __contains__(self, key):
        return key in self.dict

    def __delitem__(self, key):
        del self.dict[key]

    def __getitem__(self, key):
        return self.dict[key]

    def __iter__(self):
        return iter(self.dict)

    def __len__(self):
        return len(self.dict)

    def __setitem__(self, key, value):
        self.dict[key] = value

    def __repr__(self):
        return repr(self.dict)


class DiskCache(metaclass=StoreMeta):
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir

    def __contains__(self, key):
        with diskcache.Cache(self.cache_dir) as cache:
            return key in cache

    def __delitem__(self, key):
        with diskcache.Cache(self.cache_dir) as cache:
            del cache[key]

    def __getitem__(self, key):
        with diskcache.Cache(self.cache_dir) as cache:
            return cache[key]

    def __iter__(self):
        with diskcache.Cache(self.cache_dir) as cache:
            return iter(cache)

    def __len__(self):
        with diskcache.Cache(self.cache_dir) as cache:
            return len(cache)

    def __setitem__(self, key, value):
        with diskcache.Cache(self.cache_dir) as cache:
            cache[key] = value
