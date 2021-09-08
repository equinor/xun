from ... import serialization
from .store import NamespacedKey
from .store import Store
from .store import StoreDriver
from collections.abc import KeysView
import redis


class Redis(Store):
    def __init__(self, host=None, port=6379, db=0):
        self.host = host
        self.port = port
        self.db = db

    @property
    def driver(self):
        try:
            return self._driver
        except AttributeError:
            self._driver = RedisDriver(self.host, self.port, self.db)
            return self._driver

    def __getstate__(self):
        return super().__getstate__(), (self.host, self.port, self.db)

    def __setstate__(self, state):
        super().__setstate__(state[0])
        self.host, self.port, self.db = state[1]


class RedisDriver(StoreDriver):
    def __init__(self, host, port, db):
        self.redis = redis.Redis(host=host, port=port, db=db)

    def __contains__(self, key):
        k = key_to_redis_key(key)
        return self.redis.exists(k)

    def __delitem__(self, key):
        if key not in self:
            raise KeyError('{}'.format(key))

        k = key_to_redis_key(key)
        self.redis.delete(k)

    def __getitem__(self, key):
        if key not in self:
            raise KeyError('{}'.format(key))

        k = key_to_redis_key(key)
        v = self.redis.get(k)
        return serialization.loads(v.decode())

    def __iter__(self):
        return (redis_key_to_key(k) for k in self.redis.scan_iter())

    def __len__(self):
        return sum(1 for _ in self.__iter__())

    def __setitem__(self, key, value):
        k = key_to_redis_key(key)
        v = serialization.dumps(value)
        self.redis.set(k, v)

    def scan_namespace_iter(self, namespace):
        """ Scan Namespace iterator

        Redis scan for a namespace prefix

        Returns
        -------
        iterator
            An iterator over namespace hits
        """
        namespace_hex = encode_hex_bytes(namespace)
        pattern = b'xun:%b:*' % namespace_hex
        return self.redis.scan_iter(pattern)

    def namespace_clear(self, namespace):
        pipe = self.redis.pipeline()
        removed = list(self.scan_namespace_iter(namespace))
        for key in removed:
            pipe.delete(key)
        pipe.execute()

    def namespace_keys(self, namespace, keep_namespace=False):
        return KeysView(
            redis_key_to_key(k).key
            for k in self.scan_namespace_iter(namespace)
        )


def decode_hex_bytes(hex_bytes):
    """Decode hex bytes

    Given a byte string of a hex encoded dump, decode and load the
    serialized object.

    Parameters
    ----------
    hex_bytes : bytes
        byte string of hex encoded bytes to decode

    Returns
    -------
    Any
        Decoded python object
    """
    hex = hex_bytes.decode()
    key_string = bytes.fromhex(hex).decode()
    return serialization.loads(key_string)


def encode_hex_bytes(obj):
    """Encode hex bytes

    Given an object, serialize it to a byte-string and return the bytes
    hex-encoded

    Parameters
    ----------
    obj : Any
        Object to encode

    Return
    -------
    str
        Serialized object encoded as hex
    """
    return serialization.dumps(obj).encode().hex().encode()


def key_to_redis_key(key):
    """Key to redis key

    The reason we encode the keys as hex bytes is that the serialization string is
    raw binary data. It can contain anything, including the character : and
    even \\x00. This means that we can't split the key on : when we parse it
    back out
    """
    if isinstance(key, NamespacedKey):
        namespace = encode_hex_bytes(key.namespace)
        key = encode_hex_bytes(key.key)
        return b'xun:%b:%b' % (namespace, key)
    else:
        return encode_hex_bytes(key)


def redis_key_to_key(key):
    """Redis key to key

    See also
    --------
    key_to_redis_key
    """
    if key.startswith(b'xun:'):
        _, namespace_hex, key_hex = key.split(b':')
        namespace = decode_hex_bytes(namespace_hex)
        key = decode_hex_bytes(key_hex)
        return NamespacedKey(namespace, key)
    else:
        return decode_hex_bytes(key)
