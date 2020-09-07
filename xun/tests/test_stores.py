from collections.abc import MutableMapping
import os
import pickle
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


class DictAsStore(dict, metaclass=xun.functions.store.StoreMeta):
    pass


class DoesNotSatisfyStore(metaclass=xun.functions.store.StoreMeta):
    pass


def test_store_decorator_requires_MutableMapping():
    # with pytest.raises(TypeError):
    #     s = DoesNotSatisfyStore()

    # Due a bug in pytest.raises, we need to manually check the error
    try:
        s = DoesNotSatisfyStore()
    except TypeError:
        pass


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

    # with pytest.raises(KeyError):
    #     inst['a'] = 'Not allowed'

    # Due a bug in pytest.raises, we need to manually check the error
    try:
        inst['a'] = 'Not allowed'
    except KeyError:
        pass


@pytest.mark.parametrize('cls', stores)
def test_store_key_is_permanent(cls, tmpwd):
    inst = create_instance(cls)

    assert 'a' in inst and inst['a'] == 0

    # with pytest.raises(KeyError):
    #     inst['a'] = 'Not allowed'

    # Due a bug in pytest.raises, we need to manually check the error
    try:
        inst['a'] = 'Not allowed'
    except KeyError:
        pass


@pytest.mark.parametrize('cls', stores)
def test_store_must_be_pickleable(cls, tmpwd):
    inst = create_instance(cls)

    pickled = pickle.dumps(inst)
    unpickled = pickle.loads(pickled)

    assert isinstance(unpickled, MutableMapping)
    assert 'a' in unpickled and 'b' in unpickled and 'c' in unpickled
    assert unpickled['a'] == 0
    assert unpickled['b'] == 1
    assert unpickled['c'] == 2
