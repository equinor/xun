from ... import serialization
from ...fs.queries import parse
from abc import ABC, abstractmethod
from uuid import uuid4
import base64
import contextlib
import hashlib
import sqlite3
import struct
import threading


def restructure(data, shape):
    def shape_iter(shape, depth=0):
        if shape == ...:
            return [(), ]
        return [
            (expr.tag, *tail)
            for expr, child in shape.items()
            for tail in shape_iter(child, depth + 1)
        ]
    paths = shape_iter(shape)

    result = {} if shape != ... else set()
    for callnode, tags in data.items():
        for path in paths:
            values = [tags[p] for p in path]
            bucket = result
            if len(values) > 0:
                for value in values[:-1]:
                    bucket = bucket.setdefault(value, {})
                bucket = bucket.setdefault(values[-1], set())
            bucket.add(callnode)
    return result


def selection_from_query_syntax(query):
    def hierarchy_to_shape(hierarchies):
        if hierarchies == ...:
            return ...
        return {
            _Tag(hierarchy.expr): hierarchy_to_shape(hierarchy.children)
            for hierarchy in hierarchies
        }

    def arguments_to_conditions(arguments):
        return [_Tag(tag, op, value) for tag, op, value in arguments.args]

    args = arguments_to_conditions(query.arguments)
    tree = hierarchy_to_shape(query.hierarchy)
    return args, tree


class Store(ABC):
    @abstractmethod
    def __contains__(self, key):
        pass

    def __getitem__(self, key):
        return self.load_callnode(key)

    def __delitem__(self, key):
        return self.remove(key)

    @property
    def tags(self):
        return _Tags(self)

    @abstractmethod
    def _load_value(self, key):
        pass

    @abstractmethod
    def _load_tags(self, key):
        pass

    @abstractmethod
    def filter(self, *conditions):
        pass

    @abstractmethod
    def _store(self, key, value, **tags):
        pass

    @abstractmethod
    def remove(self, key):
        pass
    def store(self, key, value, **tags):
        if isinstance(value, serialization.Reference) and value.is_new:
            proxy_callnode = key.proxy_callnode
            value.callnode = proxy_callnode
            self._store(proxy_callnode, value._referencing)
        self._store(key, value, **tags)

    @abstractmethod
    def from_sha256(self, sha256):
        pass

    def load_callnode(self, callnode):
        result = self._load_value(callnode._replace(subscript=()))
        for subscript in callnode.subscript:
            result = result[subscript]
        if isinstance(result, serialization.Reference):
            result.store = self
        return result

    def select(self, *tag_conditions, shape=...):
        selected = self.filter(*tag_conditions)
        with_tags = {callnode: self.tags[callnode] for callnode in selected}
        return restructure(with_tags, shape)

    def query(self, query_string):
        conditions, shape = selection_from_query_syntax(parse(query_string))
        return self.select(*conditions, shape=shape)

    def guarded(self):
        return GuardedStore(self)

    def cached(self):
        return CachedStore(self)


class GuardedStore(Store):
    class StoreError(Exception):
        pass

    def __init__(self, store):
        self._wrapped_store = store
        self._written = set()

    def __contains__(self, key):
        return key in self._wrapped_store

    def _load_value(self, key):
        return self._wrapped_store._load_value(key)

    def _load_tags(self, key):
        return self._wrapped_store._load_tags(key)

    def from_sha256(self, sha256):
        return self._wrapped_store.from_sha256(key)

    def filter(self, *conditions):
        return self._wrapped_store.filter(*conditions)

    def _store(self, key, value, **tags):
        if key in self._written:
            raise self.StoreError(f'Multiple results for {key}')
        self._written.add(key)
        return self._wrapped_store._store(key, value, **tags)

    def remove(self, key):
        self._wrapped_store.remove(key)

    def guarded(self):
        return self


class CachedStore(Store):
    def __init__(self, store):
        self._wrapped_store = store
        self._cache = {}

    def __contains__(self, key):
        return key in self._wrapped_store

    def _load_value(self, key):
        try:
            return self._cache[key]
        except KeyError:
            value = self._wrapped_store._load_value(key)
            self._cache[key] = value
            return self._cache[key]

    def _load_tags(self, key):
        return self._wrapped_store._load_tags(key)

    def from_sha256(self, sha256):
        return self._wrapped_store.from_sha256(key)

    def filter(self, *conditions):
        return self._wrapped_store.filter(*conditions)

    def _store(self, key, value, **tags):
        return self._wrapped_store._store(key, value, **tags)

    def remove(self, key):
        self._wrapped_store.remove(key)

    def cached(self):
        return self


class _Tags:
    def __init__(self, store):
        self.store = store

    def __getitem__(self, key):
        if key not in self.store:
            raise KeyError(repr(key))
        return self.store._load_tags(key)

    def __getattr__(self, name):
        return _Tag(name)


class _Tag:
    def __init__(self, tag, op=None, value=None):
        if op is not None or value is not None:
            if op is None:
                raise ValueError('op must be specified if value is provided')
            if value is None:
                raise ValueError('value must be specified if op is not None')
        self.tag = tag
        self.op = op
        self.value = value

    def __call__(self, value):
        if self.op is None:
            return True
        return self.op(value, self.value)

    def __eq__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '='
        self.value = other
        return self

    def __ne__(self, other):
        raise ValueError('Cannot negate tag equality')

    def __lt__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '<'
        self.value = other
        return self

    def __le__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '<='
        self.value = other
        return self

    def __gt__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '>'
        self.value = other
        return self

    def __ge__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '>='
        self.value = other
        return self

    def __hash__(self):
        return hash((self.tag, self.op, self.value))

    def __repr__(self):
        r = f'[{self.tag}]'
        if self.op is not None:
            r += f' {self.op} {self.value}'
        return f'<tag {r}>'

    def __str__(self):
        if self.op is not None:
            return f'{self.tag}{self.op}{self.value}'
        else:
            return self.tag


class TagDB:
    @abstractmethod
    def refresh(self):
        pass

    @abstractmethod
    def dump(self, name):
        pass

    def __init__(self, store):
        self.uri = f'file:{id(store)}?mode=memory&cache=shared'
        self._lock = threading.RLock()
        self.mem = sqlite3.connect(self.uri,
                                   uri=True,
                                   isolation_level=None,
                                   check_same_thread=False)
        self.mem.executescript('''
            -- PRIVATE
            ----------

            CREATE TABLE _xun_results_table (
                journal_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                result_id BLOB NOT NULL,
                callnode TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                deleted INTEGER NOT NULL
            );

            CREATE TABLE _xun_tags_table (
                journal_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                result_id BLOB NOT NULL,
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                deleted INTEGER NOT NULL,
                FOREIGN KEY (result_id) REFERENCES _xun_results(result_id)
            );

            CREATE TABLE _xun_journal (
                journal_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                hash BLOB NOT NULL UNIQUE,
                result_journal_id INTEGER NOT NULL,
                tag_journal_id INTEGER NOT NULL
            );
            INSERT INTO _xun_journal(hash, result_journal_id, tag_journal_id)
            VALUES (X'', -1, -1);

            -- RESULTS INTERFACE
            --------------------

            CREATE VIEW _xun_results(journal_id, result_id, callnode) AS
            SELECT
                MAX(journal_id), result_id, callnode
            FROM
                _xun_results_table
            GROUP BY
                result_id,
                callnode -- ? --
            HAVING
                NOT deleted
            ORDER BY journal_id;

            CREATE TRIGGER _xun_results_insert
            INSTEAD OF INSERT ON _xun_results
            BEGIN
                INSERT INTO _xun_results_table
                    (result_id, callnode, timestamp, deleted)
                VALUES
                    (NEW.result_id, NEW.callnode, datetime('now'), 0);
            END;

            -- TAGS INTERFACE
            -----------------

            CREATE VIEW _xun_tags(journal_id, result_id, name, value) AS
            SELECT
                MAX(journal_id), result_id, name, value
            FROM
                _xun_tags_table
            GROUP BY
                result_id,
                name
            HAVING
                NOT deleted
            ORDER BY journal_id;

            CREATE TRIGGER _xun_tags_insert
            INSTEAD OF INSERT ON _xun_tags
            BEGIN
                INSERT INTO _xun_tags_table
                    (result_id, name, value, timestamp, deleted)
                VALUES
                    (NEW.result_id, NEW.name, NEW.value, datetime('now'), 0);
            END;

            CREATE TRIGGER _xun_tags_delete
            INSTEAD OF DELETE ON _xun_tags
            BEGIN
                INSERT INTO _xun_tags_table
                    (result_id, name, value, timestamp, deleted)
                VALUES
                    (OLD.result_id, OLD.name, OLD.value, datetime('now'), 1);
            END;

            -- DB INTERFACE
            ---------------

            CREATE TRIGGER _xun_delete INSTEAD OF DELETE ON _xun_results
            FOR EACH ROW
            BEGIN
                -- Mark row as deleted in _xun_results_table
                INSERT INTO _xun_results_table
                    (result_id, callnode, timestamp, deleted)
                VALUES
                    (OLD.result_id, OLD.callnode, datetime('now'), 1);

                -- Mark row as deleted in _xun_tags_table
                DELETE FROM _xun_tags WHERE result_id = OLD.result_id;
            END;
        ''')

    def __del__(self):
        self.mem.close()

    def tags(self, callnode):
        self.refresh()
        result_id = callnode.sha256(encode=False)
        result = self.mem.execute('''
            SELECT name, value FROM _xun_tags
            WHERE result_id = :result_id
        ''', {'result_id': result_id})
        return dict(result)

    def query(self, *conditions):
        self.refresh()
        joins = ' '.join(
            f'INNER JOIN [{c.tag}] ON [{c.tag}].result_id = '
            '_xun_results.result_id'
            for c in conditions
        )
        where = ' AND '.join(
            f'[{c.tag}] {c.op} :{c.tag}'
            for c in conditions
            if c.op is not None
        )
        if where:
            where = 'WHERE ' + where
        result = self.mem.execute(
            'SELECT _xun_results.callnode '
            f'from _xun_results {joins} {where}',
            {c.tag: c.value for c in conditions}
        )
        return [serialization.loads(r) for r, *_ in result if r is not None]

    def update(self, callnode, tags):
        prev_tags = self.tags(callnode)
        if prev_tags == tags:
            # Don't need a savepoint if we're not altering anything
            return

        with self.savepoint():
            if prev_tags:
                self.remove(callnode)
            result_id = callnode.sha256(encode=False)
            serialized = serialization.dumps(callnode)
            self.mem.execute('''
                INSERT INTO _xun_results(result_id, callnode)
                VALUES(:result_id, :serialized)
            ''', {
                'result_id': result_id,
                'serialized': serialized,
            })
            for tag, tag_value in tags.items():
                if '[' in tag or ']' in tag:
                    raise ValueError('tag name cannot contain "[" or "]"')
                self.mem.execute('''
                    INSERT INTO _xun_tags(result_id, name, value)
                    VALUES(:result_id, :tag, :tag_value)
                ''', {
                    'result_id': result_id,
                    'tag': tag,
                    'tag_value': tag_value,
                })
                self.create_views(tag)
        checkpoint_name = self.checkpoint()
        self.dump(checkpoint_name)

    def create_views(self, *tags):
        with self.savepoint():
            if not tags:
                tags = [
                    tag for tag, in
                    self.mem.execute('SELECT DISTINCT name FROM _xun_tags')
                ]

            for tag in tags:
                self.mem.execute(f'''
                    CREATE INDEX IF NOT EXISTS [_xun_tag_index_{tag}]
                    ON _xun_tags_table(result_id)
                    WHERE name = {self.sql_literal(tag)} AND NOT deleted
                ''')
                self.mem.execute(  #nosec
                f'''
                    CREATE VIEW IF NOT EXISTS [{tag}](result_id, [{tag}]) AS
                    SELECT
                        result_id, value
                    FROM
                        _xun_tags
                    WHERE
                        name = {self.sql_literal(tag)}
                ''')

    def unique_tags(self):
        self.refresh()
        result_id = callnode.sha256(encode=False)
        result = self.mem.execute('''
            SELECT name, value FROM _xun_tags
            WHERE result_id = :result_id
        ''', {'result_id': result_id})
        return dict(result)

    def remove(self, callnode):
        result_id = callnode.sha256(encode=False)
        with self.savepoint():
            self.mem.execute('DELETE FROM _xun_results WHERE result_id = ?',
                             (result_id,))

    def checkpoint(self):
        with self.savepoint():
            max_result_id, = self.mem.execute(
                'SELECT MAX(journal_id) FROM _xun_results_table').fetchone()
            max_tag_id, = self.mem.execute(
                'SELECT MAX(journal_id) FROM _xun_tags_table').fetchone()
            if max_result_id is None or max_tag_id is None:
                return

            _, checkpoint = self.mem.execute('''
                SELECT MAX(journal_id), hash FROM _xun_journal
            ''').fetchone()
            diff_results, diff_tags = self.diff(checkpoint)
            sha256 = self.sha256(checkpoint, *diff_results, *diff_tags)

            self.mem.execute('''
                INSERT INTO _xun_journal
                    (hash, result_journal_id, tag_journal_id)
                VALUES (?, ?, ?)
            ''', (sha256, max_result_id, max_tag_id))
        checkpoint_name = base64.urlsafe_b64encode(sha256).decode()
        return checkpoint_name

    def has_checkpoint(self, checkpoint):
        result = list(self.mem.execute(
            'SELECT * FROM _xun_journal WHERE hash = ?',
            (checkpoint,),
        ))
        return len(result) > 0

    def diff(self, checkpoint, con=None):
        if con is None:
            con = self.mem
        result_journal_id, tag_journal_id = con.execute('''
            SELECT
                result_journal_id, tag_journal_id
            FROM
                _xun_journal
            WHERE
                hash = :checkpoint
        ''', {
            'checkpoint': checkpoint,
        }).fetchone()

        results = list(con.execute('''
            SELECT
                result_id, callnode, timestamp, deleted
            FROM
                _xun_results_table
            WHERE
                journal_id > :journal_id
            ORDER BY
                timestamp, result_id
        ''', {
            'journal_id': result_journal_id,
        }))

        tags = list(con.execute('''
            SELECT
                result_id, name, value, timestamp, deleted
            FROM
                _xun_tags_table
            WHERE
                journal_id > :journal_id
            ORDER BY
                timestamp, result_id
        ''', {
            'journal_id': tag_journal_id,
        }))

        return results, tags

    def reset_to_checkpoint(self, checkpoint):
        with self.savepoint():
            result_journal_id, tag_journal_id = self.mem.execute('''
                SELECT
                    result_journal_id, tag_journal_id
                FROM
                    _xun_journal
                WHERE
                    hash = :checkpoint
            ''', {
                'checkpoint': checkpoint,
            }).fetchone()

            # Delete any rows older than the checkpoint and reset the
            # autoincrement in SQLITE_SEQUENCE. This will cause any new row
            # inserted to start incrementing from this checkpoint.

            self.mem.execute('''
                DELETE FROM _xun_results_table WHERE journal_id > :id
            ''', {
                'id': result_journal_id,
            })
            self.mem.execute('''
                UPDATE SQLITE_SEQUENCE SET SEQ=:new_journal_id
                WHERE NAME='_xun_results_table'
            ''', {
                'new_journal_id': result_journal_id,
            })

            self.mem.execute('''
                DELETE FROM _xun_tags_table WHERE journal_id > :id
            ''', {
                'id': tag_journal_id,
            })
            self.mem.execute('''
                UPDATE SQLITE_SEQUENCE SET SEQ=:new_journal_id
                WHERE NAME='_xun_tags_table'
            ''', {
                'new_journal_id': tag_journal_id,
            })

    def sql_literal(self, value):
        return self.mem.execute('SELECT QUOTE(?)', (value,)).fetchone()[0]

    def sha256(self, checkpoint, *rows):
        def coerce(obj):
            if isinstance(obj, bytes):  # BLOB type
                return obj
            elif isinstance(obj, str):  # TEXT type
                return obj.encode()
            elif isinstance(obj, type(None)):  # NULL type
                return b'\x00'
            elif isinstance(obj, int):  # INTEGER type
                return struct.pack('q', obj)
            elif isinstance(obj, float):  # REAL type
                return struct.pack('d', obj)
            else:
                raise ValueError(f'cound not coerce obj {obj}')

        sha256 = hashlib.sha256(checkpoint)
        for row in rows:
            for el in row:
                sha256.update(coerce(el))
        return sha256.digest()

    @contextlib.contextmanager
    def savepoint(self):
        try:
            self._lock.acquire()
            savepoint_name = str(uuid4())
            self.mem.execute(f'SAVEPOINT [{savepoint_name}]')
            yield
        except:
            self.mem.execute(f'ROLLBACK TO [{savepoint_name}]')
            raise
        finally:
            self.mem.execute(f'RELEASE [{savepoint_name}]')
            self._lock.release()
