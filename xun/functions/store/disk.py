from .store import Store
from .store import StoreDriver
from pathlib import Path
import hashlib
import pickle


def key_hash(key):
    pickled = pickle.dumps(key)
    return hashlib.sha256(pickled).hexdigest()


class Disk(Store):
    def __init__(self, dir):
        self.dir = Path(dir)

    @property
    def driver(self):
        try:
            return self._driver
        except AttributeError:
            self._driver = DiskDriver(self.dir)
            return self._driver

    def __getstate__(self):
        return super().__getstate__(), self.dir

    def __setstate__(self, state):
        super().__setstate__(state[0])
        self.dir = state[1]


class DiskDriver(StoreDriver):
    def __init__(self, dir):
        self.dir = dir
        self.index = {}

        (self.dir / 'keys').mkdir(parents=True, exist_ok=True)
        (self.dir / 'values').mkdir(parents=True, exist_ok=True)

    def refresh_index(self):
        files = [
            p for p in (self.dir / 'keys').iterdir() if p.is_file()
        ]
        for path in files:
            if path.name not in self.index:
                with open(str(path.resolve()), 'rb') as f:
                    try:
                        key = pickle.load(f)
                    except EOFError:
                        # This can occur if the index file is currently
                        # being written to somewhere else on the network.
                        # We consider these as not being part of the index.
                        continue

                self.index[path.name] = key

                if __debug__:
                    assert key_hash(key) == path.name
                    self.key_invariant(key)

        removed = set(self.index.keys()) - set(p.name for p in files)
        for sha256 in removed:
            key = self.index[sha256]
            del self.index[sha256]
            self.key_invariant(key)

    def key_invariant(self, key):
        sha256 = key_hash(key)
        if self.__contains__(key):
            assert not(sha256 in self.index) or self.index[sha256] == key
            assert (self.dir / 'keys' / sha256).is_file()
            assert (self.dir / 'values' / sha256).is_file()
        else:
            assert sha256 not in self.index
            assert not (self.dir / 'keys' / sha256).is_file()
            assert not (self.dir / 'values' / sha256).is_file()

    def __contains__(self, key):
        sha256 = key_hash(key)
        return (self.dir / 'keys' / sha256).is_file()

    def __delitem__(self, key):
        if __debug__:
            self.key_invariant(key)
        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        sha256 = key_hash(key)
        (self.dir / 'keys' / sha256).unlink()
        (self.dir / 'values' / sha256).unlink()
        if sha256 in self.index:
            del self.index[sha256]

    def __getitem__(self, key):
        if __debug__:
            self.key_invariant(key)
        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        sha256 = key_hash(key)
        with open(str(self.dir / 'values' / sha256), 'rb') as f:
            return pickle.load(f)

    def __iter__(self):
        self.refresh_index()
        return iter(self.index.values())

    def __len__(self):
        self.refresh_index()
        return len(self.index)

    def __setitem__(self, key, value):
        sha256 = key_hash(key)

        with open(str(self.dir / 'keys' / sha256), 'wb') as kf, \
             open(str(self.dir / 'values' / sha256), 'wb') as vf:
            pickle.dump(key, kf)
            pickle.dump(value, vf)

        self.index[sha256] = key

        if __debug__:
            self.key_invariant(key)
