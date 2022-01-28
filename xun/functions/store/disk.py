from ... import serialization
from .store import Store
from collections import namedtuple
from pathlib import Path
import contextlib
import tempfile


Paths = namedtuple('Paths', 'key val')


class Disk(Store):
    def __init__(self, dir, create_dirs=True):
        self.dir = Path(dir)
        if create_dirs:
            (self.dir / 'keys').mkdir(parents=True, exist_ok=True)
            (self.dir / 'values').mkdir(parents=True, exist_ok=True)
        elif not self.dir.exists():
            raise ValueError(f'Store Directory {str(self.dir)} does not exist')

    def paths(self, key, root=None):
        """ Key Paths

        Parameters
        ----------
        key : CallNode
            The CallNode used as key
        root : Path
            The path the key paths use as root, default is self.dir

        Returns
        -------
        (Path, Path, Path)
            The path of the key, tag, and value files respectively
        """
        if root is None:
            root = self.dir
        return Paths(key=root / 'keys' / key.sha256(),
                     val=root / 'values' / key.sha256())

    def key_invariant(self, key):
        paths = self.paths(key)
        if self.__contains__(key):
            assert paths.key.is_file()
            assert paths.val.is_file()
        else:
            assert not paths.key.is_file()
            assert not paths.val.is_file()

    def __contains__(self, key):
        return self.paths(key).key.is_file()

    def _load_value(self, key):
        if __debug__:
            self.key_invariant(key)

        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        with self.paths(key).val.open() as f:
            return serialization.load(f)

    def _load_tags(self, key):
        raise NotImplementedError

    def filter(self, *conditions):
        raise NotImplementedError

    def _store(self, key, value, **tags):
        with tempfile.TemporaryDirectory(dir=self.dir) as tmpdir:
            tmpdir = Path(tmpdir)

            temp_paths = self.paths(key, root=tmpdir)
            real_paths = self.paths(key)

            with contextlib.ExitStack() as exit_stack:
                temp_paths.key.parent.mkdir(parents=True, exist_ok=True)
                temp_paths.val.parent.mkdir(parents=True, exist_ok=True)
                key_file = exit_stack.enter_context(temp_paths.key.open('w'))
                val_file = exit_stack.enter_context(temp_paths.val.open('w'))
                serialization.dump(key, key_file)
                serialization.dump(value, val_file)
            # If succeeded, move files
            temp_paths.key.replace(real_paths.key)
            temp_paths.val.replace(real_paths.val)

        if __debug__:
            self.key_invariant(key)

    def remove(self, key):
        paths = self.paths(key)
        paths.key.unlink()
        paths.val.unlink()

    def __getstate__(self):
        return self.dir

    def __setstate__(self, state):
        self.dir = state
