from .store import Store
from .store import StoreDriver
import diskcache


class DiskCache(Store):
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir

    @property
    def driver(self):
        try:
            return self._driver
        except AttributeError:
            self._driver = DiskCacheDriver(self.cache_dir)
            return self._driver

    def __getstate__(self):
        return super().__getstate__(), self.cache_dir

    def __setstate__(self, state):
        super().__setstate__(state[0])
        self.cache_dir = state[1]


class DiskCacheDriver(StoreDriver):
    def __init__(self, cache_dir):
        self.cache = diskcache.Cache(cache_dir)

    def __contains__(self, key):
        return key in self.cache

    def __delitem__(self, key):
        del self.cache[key]

    def __getitem__(self, key):
        return self.cache[key]

    def __iter__(self):
        return iter(self.cache)

    def __len__(self):
        return len(self.cache)

    def __setitem__(self, key, value):
        self.cache[key] = value
