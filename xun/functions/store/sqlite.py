import sqlite3
import functools
import threading
from .store import Store  # Assuming Store is the superclass
from ... import serialization  # Assuming serialization is imported like this
import time

def retry(on_exceptions=()):
    class Decorator:
        def __init__(self, func):
            self.func = func

        def __call__(self, retry_delays, instance, *args, **kwargs):
            for retry_delay in retry_delays:
                try:
                    return self.func(instance, *args, **kwargs)
                except on_exceptions:
                    time.sleep(retry_delay)
            return self.func(instance, *args, **kwargs)

        def __get__(self, instance, owner):
            f = functools.partial(self, instance.retry_delays, instance)
            functools.update_wrapper(f, self.func)
            return f
    return Decorator

class SQLiteStore(Store):
    def __init__(self, db_path):
        self.local_storage = threading.local()
        self.db_path = db_path
        self.retry_delays = [0.125, 0.25, 0.5, 1, 2, 4, 8]

    def get_conn(self):
        if not hasattr(self.local_storage, 'conn'):
            self.local_storage.conn = sqlite3.connect(self.db_path, timeout=30)
            self.create_tables(self.local_storage.conn)
        return self.local_storage.conn

    def create_tables(self, conn):
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                key_hash TEXT PRIMARY KEY,
                serialized_key BLOB,
                function_name TEXT,
                function_hash TEXT
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS value_store (
                key_hash TEXT REFERENCES keys(key_hash),
                value BLOB
            );
            """)

    @retry(on_exceptions=AssertionError)
    def key_invariant(self, key):
        conn = self.get_conn()
        with conn:
            cur = conn.execute("SELECT EXISTS(SELECT 1 FROM keys WHERE key_hash=?)", (key.sha256(),))
            exists = cur.fetchone()[0]
            assert exists == (key in self)

    def __contains__(self, key):
        conn = self.get_conn()
        with conn:
            cur = conn.execute("SELECT EXISTS(SELECT 1 FROM keys WHERE key_hash=?)", (key.sha256(),))
            return cur.fetchone()[0]

    @retry(on_exceptions=(KeyError, sqlite3.Error))
    def _load_value(self, key):
        if __debug__:
            self.key_invariant(key)

        if key not in self:
            raise KeyError(f'KeyError: {str(key)}')

        conn = self.get_conn()
        with conn:
            cur = conn.execute("SELECT value FROM value_store WHERE key_hash=?", (key.sha256(),))
            value = cur.fetchone()[0]
            return serialization.loads(value)

    def _store(self, key, value, **tags):
        serialized_value = serialization.dumps(value)
        serialized_key = serialization.dumps(key)
        function_name = getattr(key, 'function_name', None)
        function_hash = getattr(key, 'function_hash', None)

        conn = self.get_conn()
        with conn:
            conn.execute("""
            INSERT OR IGNORE INTO keys (key_hash, serialized_key, function_name, function_hash)
            VALUES (?, ?, ?, ?)
            """, (key.sha256(), serialized_key, function_name, function_hash))
            conn.execute("INSERT OR REPLACE INTO value_store (key_hash, value) VALUES (?, ?)", (key.sha256(), serialized_value))

        if __debug__:
            self.key_invariant(key)

    def remove(self, key):
        conn = self.get_conn()
        with conn:
            conn.execute("DELETE FROM value_store WHERE key_hash=?", (key.sha256(),))
            conn.execute("DELETE FROM keys WHERE key_hash=?", (key.sha256(),))

    def _load_tags(self, key):
        raise NotImplementedError

    def filter(self, *conditions):
        raise NotImplementedError

    def load_values_by_function_hash(self, function_hash):
        conn = self.get_conn()
        results = []
        with conn:
            cur = conn.execute("""
            SELECT value_store.value
            FROM value_store
            JOIN keys ON value_store.key_hash = keys.key_hash
            WHERE keys.function_hash = ?
            """, (function_hash,))
            for row in cur.fetchall():
                serialized_value = row[0]
                value = serialization.loads(serialized_value)
                results.append(value)
        return results

    def __getstate__(self):
        return self.db_path, self.retry_delays

    def __setstate__(self, state):
        self.db_path, self.retry_delays = state
        self.local_storage = threading.local()
