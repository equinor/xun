from collections.abc import MutableMapping
import diskcache
import functools


def store(orig_class):
    cls = orig_class
    if not issubclass(cls, MutableMapping):
        cls = type(cls.__name__, (cls, MutableMapping), {})

    class _store_wrapper:
        def __init__(self, *args, **kwargs):
            self._store_wrapped = cls(*args, **kwargs)
            self._store_deleted = set()

        def __getattr__(self, name):
            return getattr(self._store_wrapped, name)

        def __contains__(self, key):
            return key in self._store_wrapped

        def __delitem__(self, key):
            self._store_wrapped.__delitem__(key)
            self._store_deleted.add(key)

        def __getitem__(self, key):
            if key in self._store_deleted:
                raise KeyError('{} has been deleted'.format(key))
            print('key:', key, 'store:', self._store_wrapped)
            return self._store_wrapped.__getitem__(key)

        def __setitem__(self, key, value):
            if key in self._store_deleted:
                raise KeyError('{} has been deleted'.format(key))
            if key in self._store_wrapped:
                raise KeyError('{} already set'.format(key))
            return self._store_wrapped.__setitem__(key, value)

    functools.update_wrapper(_store_wrapper, orig_class, updated=())
    MutableMapping.register(_store_wrapper)
    return _store_wrapper


@store
class Memory(dict):
    pass


@store
class DiskCache:
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
