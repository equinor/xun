from .store import Store
from .store import StoreDriver
from pathlib import Path
import hashlib
import paramiko
import pickle
import stat


def key_hash(key):
    pickled = pickle.dumps(key)
    return hashlib.sha256(pickled).hexdigest()


class SFTP(Store):
    def __init__(self,
                 host,
                 root,
                 port=22,
                 username=None,
                 missing_host_key_policy=paramiko.WarningPolicy()):
        self.host = host
        self.port = port
        self.root = Path(root)
        self.username = username
        self.missing_host_key_policy = missing_host_key_policy

    @property
    def driver(self):
        try:
            return self._driver
        except AttributeError:
            self._driver = SFTPDriver(self.host, self.port, self.root,
                                      self.username,
                                      self.missing_host_key_policy)
            return self._driver

    def __getstate__(self):
        return super().__getstate__(
        ), self.host, self.port, self.root, self.username, self.missing_host_key_policy

    def __setstate__(self, state):
        super().__setstate__(state[0])
        self.host = state[1]
        self.port = state[2]
        self.root = state[3]
        self.username = state[4]
        self.missing_host_key_policy = state[5]


class SFTPDriver(StoreDriver):

    _connection_pool = {}

    def __init__(self, host, port, root, username, missing_host_key_policy):
        self.host = host
        self.port = port
        self.root = root
        self.username = username
        self.missing_host_key_policy = missing_host_key_policy
        self.index = {}

        self._ssh = None
        self._sftp = None

    @property
    def ssh(self):
        # We reuse ssh connections, note that these connections are left open
        # for the duration of the process. We should consider changing store
        # semantics to make cleanup a part of the natural usage.
        if self._ssh is not None:
            return self._ssh
        try:
            self._ssh = SFTPDriver._connection_pool[hash(self)]
            return self._ssh
        except KeyError:
            pass

        self._ssh = SFTPDriver._connection_pool[
            hash(self)] = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(self.missing_host_key_policy)
        self._ssh.connect(self.host,
                          port=self.port,
                          username=self.username,
                          allow_agent=False,
                          look_for_keys=True)
        return self._ssh

    @property
    def sftp(self):
        if self._sftp is None:
            assert self.ssh.get_transport() != None
            self._sftp = self.ssh.open_sftp()
            if not self.is_dir(self.root / 'values'):
                self._sftp.mkdir(str(self.root / 'values'), mode=0o711)
            if not self.is_dir(self.root / 'keys'):
                self._sftp.mkdir(str(self.root / 'keys'), mode=0o711)
        return self._sftp

    def is_dir(self, path):
        try:
            return stat.S_ISDIR(self.sftp.stat(str(path)).st_mode)
        except FileNotFoundError:
            return False

    def is_file(self, path):
        try:
            return stat.S_ISREG(self.sftp.stat(str(path)).st_mode)
        except FileNotFoundError:
            return False

    def refresh_index(self):
        files = list(self.key_files())
        for path in files:
            if path.name not in self.index:
                with self.sftp.open(str(path), 'rb') as f:
                    key = pickle.load(f)
                self.index[path.name] = key
                if __debug__:
                    assert key_hash(key) == path.name
                    self.key_invariant(key)

        removed = set(self.index.keys()) - set(p.name for p in files)
        for sha256 in removed:
            key = self.index[sha256]
            del self.index[sha256]
            self.key_invariant(key)

    def key_files(self):
        return (
            Path(self.root / 'keys' / p)
            for p in self.sftp.listdir(str(self.root / 'keys'))
            if self.is_file(self.root / 'keys' / p)
        )

    def key_invariant(self, key):
        sha256 = key_hash(key)
        if self.__contains__(key):
            assert not(sha256 in self.index) or self.index[sha256] == key
            assert self.is_file(self.root / 'keys' / sha256)
            assert self.is_file(self.root / 'values' / sha256)
        else:
            print(self.index)
            assert sha256 not in self.index
            assert not self.is_file(self.root / 'keys' / sha256)
            assert not self.is_file(self.root / 'values' / sha256)

    def __contains__(self, key):
        sha256 = key_hash(key)
        return self.is_file(self.root / 'keys' / sha256)

    def __delitem__(self, key):
        if __debug__:
            self.key_invariant(key)
        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        sha256 = key_hash(key)
        self.sftp.remove(str(self.root / 'keys' / sha256))
        self.sftp.remove(str(self.root / 'values' / sha256))
        if sha256 in self.index:
            del self.index[sha256]

    def __getitem__(self, key):
        if __debug__:
            self.key_invariant(key)
        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        sha256 = key_hash(key)
        with self.sftp.open(str(self.root / 'values' / sha256), 'rb') as f:
            return pickle.load(f)

    def __iter__(self):
        self.refresh_index()
        return iter(self.index.values())

    def __len__(self):
        self.refresh_index()
        return len(self.index)

    def __setitem__(self, key, value):
        sha256 = key_hash(key)

        with self.sftp.open(str(self.root / 'keys' / sha256), 'wb') as kf, \
             self.sftp.open(str(self.root / 'values' / sha256), 'wb') as vf:
            pickle.dump(key, kf)
            pickle.dump(value, vf)

        self.index[sha256] = key

        if __debug__:
            self.key_invariant(key)

    def __hash__(self):
        return hash((self.host, self.port, self.root, self.username))
