from abc import ABCMeta
from collections.abc import MutableMapping
import copyreg
import diskcache
import functools
import pickle


def patch(attrib_dict):
    def patch_internal(func):
        if func.__name__ in attrib_dict:
            attrib_dict[func.__name__] = func
    return patch_internal


class StoreMeta(ABCMeta):
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


class Memory(dict, metaclass=StoreMeta):
    pass


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
