from ... import serialization
from .disk import key_hash_str
from .store import Store
from pathlib import Path
import paramiko
import stat
import tempfile


class SFTP(Store):

    _connection_pool = {}

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

    def key_invariant(self, key):
        b64 = key_hash_str(key)
        if self.__contains__(key):
            assert self.is_file(self.root / 'keys' / b64)
            assert self.is_file(self.root / 'values' / b64)
        else:
            assert not self.is_file(self.root / 'keys' / b64)
            assert not self.is_file(self.root / 'values' / b64)

    def __contains__(self, key):
        b64 = key_hash_str(key)
        return self.is_file(self.root / 'keys' / b64)

    def load(self, key):
        if __debug__:
            self.key_invariant(key)
        if not self.__contains__(key):
            raise KeyError('KeyError: {}'.format(str(key)))

        b64 = key_hash_str(key)
        with self.sftp.open(str(self.root / 'values' / b64), 'r') as f:
            return serialization.load(f)

    def metadata(self, key):
        raise NotImplementedError

    def store(self, key, value, **metadata):
        b64 = key_hash_str(key)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            key_tmpfile = (tmpdir / b64).with_suffix('.key')
            val_tmpfile = (tmpdir / b64).with_suffix('.value')
            with key_tmpfile.open('w') as kf, val_tmpfile.open('w') as vf:
                serialization.dump(key, kf)
                serialization.dump(value, vf)
            # If succeeded, move files
            self.sftp.put(str(key_tmpfile), str(self.root / 'keys' / b64))
            self.sftp.put(str(val_tmpfile), str(self.root / 'values' / b64))

        if __debug__:
            self.key_invariant(key)

    def __hash__(self):
        return hash((self.host, self.port, self.root, self.username))

    def __getstate__(self):
        return (self.host,
                self.port,
                self.root,
                self.username,
                self.missing_host_key_policy)

    def __setstate__(self, state):
        self.host = state[0]
        self.port = state[1]
        self.root = state[2]
        self.username = state[3]
        self.missing_host_key_policy = state[4]

        self._ssh = None
        self._sftp = None
