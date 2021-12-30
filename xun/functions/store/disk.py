from ... import serialization
from .store import Store
from .store import TagDB
from collections import namedtuple
from pathlib import Path
import base64
import contextlib
import sqlite3
import tempfile


Paths = namedtuple('Paths', 'key val')


class Disk(Store):
    def __init__(self, dir):
        self.dir = Path(dir)
        (self.dir / 'keys').mkdir(parents=True, exist_ok=True)
        (self.dir / 'values').mkdir(parents=True, exist_ok=True)
        self._tagdb = DiskTagDB(self)

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
        return self._tagdb.tags(key)

    def filter(self, *conditions):
        return self._tagdb.query(*conditions)

    def store(self, key, value, **tags):
        self._tagdb.update(key, tags)

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
        self._tagdb.remove(key)

    def __getstate__(self):
        return self.dir

    def __setstate__(self, state):
        self.dir = state
        self._tagdb = DiskTagDB(self)


class DiskTagDB(TagDB):
    def __init__(self, store):
        super().__init__(store)
        self.dir = store.dir / 'db'
        self.dir.mkdir(parents=True, exist_ok=True)

    def refresh(self):
        reconciled = False
        with contextlib.ExitStack() as stack:
            stack.enter_context(self.savepoint())
            databases = {}
            for f in self.dir.iterdir():
                checkpoint_hash = base64.urlsafe_b64decode(f.name.encode())
                if f.is_file() and not self.has_checkpoint(checkpoint_hash):
                    try:
                        uri = f'file:{str(f)}?mode=ro'

                        # Connecting to the database opens a file handle. In
                        # the case of the file being deleted, we still have a
                        # handle to it and can read from it.
                        con = sqlite3.connect(uri, uri=True)

                        # Attach our memory database to this connection
                        # imediately as this will fail with a DatabaseError if
                        # the database we just connected to is not a valid
                        # database.
                        con.execute(
                            f'ATTACH DATABASE \'{self.uri}\' AS _xun_main'
                        )

                        # Keep connections (and file handles) alive until we
                        # leave the context
                        ctx = contextlib.closing(con)
                        databases[f] = stack.enter_context(ctx)
                    except sqlite3.OperationalError:
                        pass  # Database was deleted before we could connect
                    except sqlite3.DatabaseError:
                        pass  # File is not a database
            for con in databases.values():
                self.reconcile(con, read_from=None, write_to='_xun_main')
                reconciled = True

        if reconciled:
            self.checkpoint()

        # Now that our changes have been reconciled and dumped. Delete any
        # databases ours is comprising.
        for db in databases:
            db.unlink()

    def reconcile(self, con, read_from=None, write_to=None):
        if read_from is None and write_to is None:
            raise ValueError('Cannot read and write to main database')

        def latest_common_checkpoint():
            _, checkpoint = con.execute('''
                SELECT MAX(this.journal_id), this.hash
                FROM _xun_main._xun_journal AS this
                INNER JOIN _xun_journal as other
                ON
                    this.hash = other.hash AND
                    this.journal_id = other.journal_id
            ''').fetchone()
            return checkpoint

        with self.savepoint():
            checkpoint = latest_common_checkpoint()

            diff_con_results, diff_con_tags = self.diff(checkpoint, con=con)
            diff_mem_results, diff_mem_tags = self.diff(checkpoint)

            new_results = sorted(
                diff_con_results + diff_mem_results,
                key=lambda el: (el[3], el[1])
            )
            new_tags = sorted(
                diff_con_tags + diff_mem_tags,
                key=lambda el: (el[4], el[1])
            )

            self.reset_to_checkpoint(checkpoint)

            self.mem.executemany('''
                INSERT INTO _xun_results_table
                    (result_id, callnode, timestamp, deleted)
                VALUES
                    (?, ?, ?, ?)
            ''', new_results)
            self.mem.executemany('''
                INSERT INTO _xun_tags_table
                    (result_id, name, value, timestamp, deleted)
                VALUES
                    (?, ?, ?, ?, ?)
            ''', new_tags)

    def dump(self, name):
        if self.mem.in_transaction:
            raise RuntimeError('Database Busy')
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            tmp = tmpdir / 'sql'
            with contextlib.closing(sqlite3.connect(tmp)) as bck:
                self.mem.backup(bck)
            tmp.replace(self.dir / name)
