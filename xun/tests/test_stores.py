from collections.abc import MutableMapping
from contextlib import contextmanager
from unittest import mock
from xun.functions import CopyError
import contextlib
import copy
import mockssh
import paramiko
import pickle
import pytest
import tempfile
import xun


# Stores to test


@contextmanager
def Azure():
    store = xun.functions.Store.Azure('xunstoragetest')
    yield store


@contextmanager
def Memory():
    store = xun.functions.store.Memory()
    yield store


@contextmanager
def TmpDisk():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield xun.functions.store.Disk(tmpdirname)


@contextmanager
def TmpSFTP():
    users = {'ssh-user': 'xun/tests/test_data/ssh/id_rsa'}
    with contextlib.ExitStack() as stack:
        tmpdirname = stack.enter_context(tempfile.TemporaryDirectory())
        server = stack.enter_context(mockssh.Server(users))
        client = stack.enter_context(server.client('ssh-user'))

        ssh_mock = stack.enter_context(
            mock.patch('xun.functions.store.sftp.SFTP.ssh',
                       new_callable=mock.PropertyMock))
        ssh_mock.return_value = client

        store = xun.functions.store.SFTP(
            '127.0.0.1',
            tmpdirname,
            username='ssh-user',
            missing_host_key_policy=paramiko.MissingHostKeyPolicy())
        yield store


stores = [
    Azure,
    Memory,
    TmpDisk,
    TmpSFTP,
]

# ^ Stores to test


@contextlib.contextmanager
def create_instance(cls):
    data = {'a': 0, 'b': 1, 'c': 2}
    with cls() as inst:
        for key, value in data.items():
            inst.store(key, value)
        yield inst


@pytest.mark.parametrize('cls', stores)
def test_store_implementation(cls):
    with cls() as store:
        store.store('a', 0)
        store.store('b', 1)
        store.store('c', 2)

        assert 'a' in store
        assert 'b' in store
        assert 'c' in store

        store['a'] == 0
        store['b'] == 1
        store['c'] == 2


@pytest.mark.parametrize('cls', stores)
def test_store_metadata(cls):
    with cls() as store:
        pass


@pytest.mark.parametrize('cls', stores)
def test_store_must_be_picklable(cls):
    if cls is Memory or (hasattr(cls, 'parent') and cls.parent is Memory):
        pytest.skip('Cannot transport in-memory store')
    with create_instance(cls) as store:
        pickled = pickle.dumps(store)
        unpickled = pickle.loads(pickled)

        assert 'a' in unpickled and 'b' in unpickled and 'c' in unpickled
        assert unpickled['a'] == 0
        assert unpickled['b'] == 1
        assert unpickled['c'] == 2

        store.store('d', 3)
        assert unpickled['d'] == 3

        unpickled.store('e', 4)
        assert store['e'] == 4


def test_memory_store_not_picklable():
    store = xun.functions.store.Memory()

    with pytest.raises(CopyError):
        copy.copy(store)
    with pytest.raises(CopyError):
        copy.deepcopy(store)
    with pytest.raises(CopyError):
        pickle.dumps(store)


def test_sftp_driver_is_complatible_with_disk_driver():
    with create_instance(TmpSFTP) as sftp:
        disk = xun.functions.store.Disk(sftp.root)
        assert disk['a'] == 0
        assert disk['b'] == 1
        assert disk['c'] == 2


@pytest.mark.parametrize('cls', stores)
def test_store_query(cls):
    with create_instance(cls) as store:
        result = store.query("""
            username=xun start_time>=2020-01-01 entrypoint => starttime {
                entrypoint
            }
        """)

        assert result == {
            ...
        }
