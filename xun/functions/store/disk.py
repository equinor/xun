from .store import Store
from .store import StoreDriver
from pathlib import Path
import base64
import hashlib
import pickle


def key_hash_str(key):
    pickled = pickle.dumps(key)
    sha256 = hashlib.sha256()
    sha256.update(pickled)
    truncated = sha256.digest()[:12]
    return base64.urlsafe_b64encode(truncated).decode()


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
                    assert key_hash_str(key) == path.name
                    self.key_invariant(key)

        removed = set(self.index.keys()) - set(p.name for p in files)
        for b64 in removed:
            key = self.index[b64]
            del self.index[b64]
            self.key_invariant(key)

    def key_invariant(self, key):
        b64 = key_hash_str(key)
        if self.__contains__(key):
            assert not(b64 in self.index) or self.index[b64] == key
            assert (self.dir / 'keys' / b64).is_file()
            assert (self.dir / 'values' / b64).is_file()
        else:
            assert b64 not in self.index
            assert not (self.dir / 'keys' / b64).is_file()
            assert not (self.dir / 'values' / b64).is_file()

    def __contains__(self, key):
        b64 = key_hash_str(key)
        return (self.dir / 'keys' / b64).is_file()

    def __delitem__(self, key):
        if __debug__:
            self.key_invariant(key)
        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        b64 = key_hash_str(key)
        (self.dir / 'keys' / b64).unlink()
        (self.dir / 'values' / b64).unlink()
        if b64 in self.index:
            del self.index[b64]

    def __getitem__(self, key):
        if __debug__:
            self.key_invariant(key)
        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        b64 = key_hash_str(key)
        with open(str(self.dir / 'values' / b64), 'rb') as f:
            return pickle.load(f)

    def __iter__(self):
        self.refresh_index()
        return iter(self.index.values())

    def __len__(self):
        self.refresh_index()
        return len(self.index)

    def __setitem__(self, key, value):
        b64 = key_hash_str(key)

        with open(str(self.dir / 'keys' / b64), 'wb') as kf, \
             open(str(self.dir / 'values' / b64), 'wb') as vf:
            pickle.dump(key, kf)
            pickle.dump(value, vf)

        self.index[b64] = key

        if __debug__:
            self.key_invariant(key)
