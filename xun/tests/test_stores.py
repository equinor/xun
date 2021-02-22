from .helpers import FakeRedis
from collections.abc import MutableMapping
from contextlib import contextmanager
from unittest import mock
from xun.functions import CopyError
from xun.functions.store import NamespacedKey
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
            mock.patch('xun.functions.store.sftp.SFTPDriver.ssh',
                       new_callable=mock.PropertyMock))
        ssh_mock.return_value = client

        store = xun.functions.store.SFTP(
            '127.0.0.1',
            tmpdirname,
            username='ssh-user',
            missing_host_key_policy=paramiko.MissingHostKeyPolicy())
        yield store


def with_namespace(cls, namespace):
    @contextmanager
    def ctx():
        with cls() as store:
            # Values in the original namespace should not be visible in the
            # namespace
            store.update(some_garbage=-1)

            yield store / namespace
    ctx.__name__ = 'Namespaced_{}_{}'.format(cls.__name__, namespace)
    ctx.parent = cls
    return ctx


stores = [
    Memory,
    FakeRedis,
    TmpDisk,
    TmpSFTP,
    with_namespace(Memory, 'test_namespace'),
    with_namespace(FakeRedis, 'test_namespace'),
    with_namespace(TmpDisk, 'test_namespace'),
    with_namespace(TmpSFTP, 'test_namespace'),
]

# ^ Stores to test


def create_instance(cls):
    data = {'a': 0, 'b': 1, 'c': 2}
    inst = cls()
    for key, value in data.items():
        inst[key] = value
    return inst


class DoesNotSatisfyStore(xun.functions.store.Store):
    pass


def test_store_decorator_requires_MutableMapping():
    with pytest.raises(TypeError):
        DoesNotSatisfyStore()


@pytest.mark.parametrize('cls', stores)
def test_store_is_collection(cls):
    with cls() as store:
        store.update(a=0, b=1, c=2)

        assert isinstance(store, MutableMapping)
        assert store['a'] == 0
        assert store['b'] == 1
        assert store['c'] == 2

        assert set(store.keys()) >= {'a', 'b', 'c'}


@pytest.mark.parametrize('cls', stores)
def test_store_driver_is_collection(cls):
    with cls() as store:
        driver = store.driver
        driver.update(a=0, b=1, c=2)

        assert isinstance(driver, MutableMapping)
        assert driver['a'] == 0
        assert driver['b'] == 1
        assert driver['c'] == 2

        assert set(driver.keys()) >= {'a', 'b', 'c'}


@pytest.mark.parametrize('cls', stores)
def test_store_must_be_picklable(cls):
    if cls is Memory or (hasattr(cls, 'parent') and cls.parent is Memory):
        pytest.skip('Cannot transport in-memory store')
    with cls() as store:
        store.update(a=0, b=1, c=2)

        pickled = pickle.dumps(store)
        unpickled = pickle.loads(pickled)

        assert isinstance(unpickled, MutableMapping)
        assert 'a' in unpickled and 'b' in unpickled and 'c' in unpickled
        assert unpickled['a'] == 0
        assert unpickled['b'] == 1
        assert unpickled['c'] == 2

        store['d'] = 3
        assert unpickled['d'] == 3

        unpickled['e'] = 4
        assert store['e'] == 4


@pytest.mark.parametrize('cls', stores)
def test_store_namespaces(cls):
    with cls() as store:
        animals = store / 'animals'

        # Test namespaced namespaces
        cats = store / 'animals' / 'cats'

        store['a'] = 1
        store['b'] = 2

        animals['a'] = 3
        animals['c'] = 4

        cats['a'] = 5
        cats['d'] = 6

        assert sorted(animals) == ['a', 'c']
        assert sorted(cats) == ['a', 'd']

        assert store['a'] == 1
        assert store['b'] == 2
        assert animals['a'] == 3
        assert animals['c'] == 4
        assert cats['a'] == 5
        assert cats['d'] == 6

        assert store[NamespacedKey(('animals',), 'a')] == 3
        assert store[NamespacedKey(('animals',), 'c')] == 4
        assert store[NamespacedKey(('animals', 'cats'), 'a')] == 5
        assert store[NamespacedKey(('animals', 'cats'), 'd')] == 6

        assert animals / 'cats' == cats

        cats.clear()
        assert sorted(animals) == ['a', 'c']


@pytest.mark.parametrize('cls', stores)
def test_store_floordiv_getitem(cls):
    with cls() as store:
        store.update(a=0, b=1, c=2)

        assert store // 'a' == 0
        assert store // 'b' == 1
        assert store // 'c' == 2


@pytest.mark.parametrize('cls', stores)
def test_store_mutable_mapping(cls):
    with cls() as store:
        store.update(a=0, b=1, c=2)

        # __contains__
        assert 'a' in store and 'b' in store and 'c' in store
        assert 'd' not in store

        # __delitem__
        del store['a']
        assert 'a' not in store
        with pytest.raises(KeyError):
            store['a']
        with pytest.raises(KeyError):
            del store['a']

        # __eq__
        with cls() as other:
            other.update(b=1, c=2)
            assert store == other

        # __getitem__
        assert store['b'] == 1
        assert store['c'] == 2

        # __iter__
        assert sorted(k for k in iter(store)) == ['b', 'c']

        # __len__
        assert len(store) == 2

        # __ne__
        with cls() as other:
            assert store != other

        # __setitem__
        store['a'] = 3
        store['b'] = 4
        store['c'] = 5
        store['d'] = 6
        assert store['a'] == 3
        assert store['b'] == 4
        assert store['c'] == 5
        assert store['d'] == 6

        # get
        assert store.get('a') == 3
        assert store.get('e', default='default') == 'default'
        assert store.get('e') is None

        # items
        assert (
            sorted(store.items()) ==
            [('a', 3), ('b', 4), ('c', 5), ('d', 6)]
        )

        # keys
        assert sorted(store.keys()) == ['a', 'b', 'c', 'd']

        # pop
        assert store.pop('a') == 3
        assert store.pop('e', default='default') == 'default'
        assert 'a' not in store
        assert 'e' not in store

        # popitem
        items = set(store.items())
        popped = store.popitem()
        assert popped in items
        assert popped[0] not in store

        # setdefault
        value = store.setdefault(popped[0], default=popped[1])
        assert value == popped[1]
        assert store[popped[0]] == popped[1]
        assert store.setdefault('b', default=None) == 4

        # clear
        store.clear()
        assert len(store) == 0
        assert dict(store.items()) == {}


def test_memory_store_not_picklable():
    store = xun.functions.store.Memory()

    with pytest.raises(CopyError):
        copy.copy(store)
    with pytest.raises(CopyError):
        copy.deepcopy(store)
    with pytest.raises(CopyError):
        pickle.dumps(store)


def test_sftp_driver_is_complatible_with_disk_driver():
    with TmpSFTP() as sftp:
        sftp.update(a=0, b=1, c=2)

        disk = xun.functions.store.Disk(sftp.root)
        assert disk // 'a' == 0
        assert disk // 'b' == 1
        assert disk // 'c' == 2
