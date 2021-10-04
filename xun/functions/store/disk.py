from ... import serialization
from .store import Store
from pathlib import Path
import base64
import hashlib
import tempfile


def key_hash_str(key):
    serialized = serialization.dumps(key).encode()
    sha256 = hashlib.sha256()
    sha256.update(serialized)
    truncated = sha256.digest()
    return base64.urlsafe_b64encode(truncated).decode()


class Disk(Store):
    def __init__(self, dir):
        self.dir = Path(dir)
        (self.dir / 'keys').mkdir(parents=True, exist_ok=True)
        (self.dir / 'values').mkdir(parents=True, exist_ok=True)

    def key_invariant(self, key):
        b64 = key_hash_str(key)
        if self.__contains__(key):
            assert (self.dir / 'keys' / b64).is_file()
            assert (self.dir / 'values' / b64).is_file()
        else:
            assert not (self.dir / 'keys' / b64).is_file()
            assert not (self.dir / 'values' / b64).is_file()

    def __contains__(self, key):
        b64 = key_hash_str(key)
        return (self.dir / 'keys' / b64).is_file()

    def load(self, key):
        if __debug__:
            self.key_invariant(key)
        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        b64 = key_hash_str(key)
        with (self.dir / 'values' / b64).open() as f:
            return serialization.load(f)

    def metadata(self, key):
        raise NotImplementedError

    def store(self, key, value, **metadata):
        b64 = key_hash_str(key)

        with tempfile.TemporaryDirectory(dir=self.dir) as tmpdir:
            tmpdir = Path(tmpdir)
            key_tmpfile = (tmpdir / b64).with_suffix('.key')
            val_tmpfile = (tmpdir / b64).with_suffix('.value')
            with key_tmpfile.open('w') as kf, val_tmpfile.open('w') as vf:
                serialization.dump(key, kf)
                serialization.dump(value, vf)
            # If succeeded, move files
            key_tmpfile.replace(self.dir / 'keys' / b64)
            val_tmpfile.replace(self.dir / 'values' / b64)

        if __debug__:
            self.key_invariant(key)

    def __getstate__(self):
        return self.dir

    def __setstate__(self, state):
        self.dir = state
