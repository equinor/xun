import pickle
import redis
from collections.abc import MutableMapping


class Redis(MutableMapping):
    def __init__(self, host=None, port=6379, db=0):
        self.host = host
        self.port = port
        self.db = db
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db
            )
        return self._redis

    def __contains__(self, key):
        k = pickle.dumps(key)
        return self.redis.exists(k)

    def __delitem__(self, key):
        if not self.__contains__(key):
            raise KeyError('{}'.format(key))

        k = pickle.dumps(key)
        self.redis.delete(k)

    def __getitem__(self, key):
        if not self.__contains__(key):
            raise KeyError('{}'.format(key))\

        k = pickle.dumps(key)
        v = self.redis.get(k)
        return pickle.loads(v)

    def __iter__(self):
        return (pickle.loads(v) for v in self.redis.scan_iter())

    def __len__(self):
        return len(list(self.__iter__()))

    def __setitem__(self, key, value):
        k = pickle.dumps(key)
        v = pickle.dumps(value)
        self.redis.set(k, v)

    def __getstate__(self):
        return (self.host, self.port, self.db)

    def __setstate__(self, state):
        self.host = state[0]
        self.port = state[1]
        self.db = state[2]
        self._redis = None
