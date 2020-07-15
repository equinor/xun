from .helpers import tmpwd
from collections.abc import MutableMapping
import os
import pytest
import xun


stores = [
    xun.functions.store.Memory,

    # working directory is assumed to be tmp
    lambda: xun.functions.store.DiskCache(os.getcwd()),
]


def create_instance(cls):
    data = {'a': 0, 'b': 1, 'c': 2}
    inst = cls()
    for key, value in data.items():
        inst[key] = value
    return inst


@xun.functions.store.store
class DictAsStore(dict):
    pass


@xun.functions.store.store
class DoesNotSatisfyStore:
    pass


def test_store_decorator_requires_MutableMapping():
    with pytest.raises(TypeError):
        s = DoesNotSatisfyStore()


def test_store_decorator_dict_satisifies_MutableMapping():
    s = DictAsStore()
    assert isinstance(s, MutableMapping)


@pytest.mark.parametrize('cls', stores)
def test_store_is_collection(cls, tmpwd):
    inst = create_instance(cls)

    assert isinstance(inst, MutableMapping)
    assert 'a' in inst and 'b' in inst and 'c' in inst
    assert inst['a'] == 0
    assert inst['b'] == 1
    assert inst['c'] == 2


@pytest.mark.parametrize('cls', stores)
def test_store_delete_is_permanent(cls, tmpwd):
    inst = create_instance(cls)

    del inst['a']

    assert 'a' not in inst
    assert 'b' in inst and 'c' in inst

    with pytest.raises(KeyError):
        inst['a'] = 'Not allowed'


@pytest.mark.parametrize('cls', stores)
def test_store_key_is_permanent(cls, tmpwd):
    inst = create_instance(cls)

    assert 'a' in inst and inst['a'] == 0

    with pytest.raises(KeyError):
        inst['a'] = 'Not allowed'
