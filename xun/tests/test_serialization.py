from datetime import datetime
from immutables import Map as frozenmap
import numpy as np
import os
import pandas as pd
import pathlib
import pytest
import xun


def test_serialization():
    recursive_dict = {1: 1}
    recursive_dict['self'] = recursive_dict
    yml = xun.serialization.dumps(recursive_dict)
    loaded = xun.serialization.loads(yml)

    assert loaded[1] == 1
    assert loaded['self'] is loaded


def test_hash_is_order_independent():
    class A(metaclass=xun.serialization.functor.IsoFunctor):
        def __call__(cls, value):
            return value + 1

        def __invert__(cls):
            return B

    class B(metaclass=xun.serialization.functor.IsoFunctor):
        def __call__(cls, value):
            return value - 1

        def __invert__(cls):
            return A

    assert A.hash == B.hash


def test_serialization_binary():
    b = os.urandom(128)
    yml = xun.serialization.dumps(b)
    loaded = xun.serialization.loads(yml)
    assert loaded == b


def test_serialization_tuple():
    value = ('hello', 'world', 1, 2, 3)
    yml = xun.serialization.dumps(value)
    loaded = xun.serialization.loads(yml)
    assert loaded == value


def test_serialization_set():
    value = {'hello', 'world', 1, 2, 3}
    yml = xun.serialization.dumps(value)
    loaded = xun.serialization.loads(yml)
    assert loaded == value


def test_serialization_frozenset():
    value = frozenset({'hello', 'world', 1, 2, 3})
    yml = xun.serialization.dumps(value)
    loaded = xun.serialization.loads(yml)
    assert loaded == value


def test_serialization_frozenmap():
    value = frozenmap({'hello': 'world', 0: 1})
    yml = xun.serialization.dumps(value)
    loaded = xun.serialization.loads(yml)
    assert loaded == value


def test_serialization_pathlib():
    path = pathlib.Path('/hello/world')
    yml = xun.serialization.dumps(path)
    loaded = xun.serialization.loads(yml)
    assert loaded == path


def test_namespacedkey_serialization():
    key = xun.functions.store.NamespacedKey(('animals',), 'a')
    yml = xun.serialization.dumps([key, key])
    loaded = xun.serialization.loads(yml)
    assert loaded[0] == key
    assert loaded[1] == key
    assert loaded[0] is loaded[1]


def test_callnode_serialization():
    cn = xun.functions.CallNode('function_name',
                                'hash',
                                None,
                                1,
                                2,
                                {1: 2},
                                hello='world')
    yml = xun.serialization.dumps(cn)
    loaded = xun.serialization.loads(yml)
    assert loaded == cn


def test_pandas_series_serialization():
    series = pd.Series(np.random.randn(10))
    yml = xun.serialization.dumps(series)
    loaded = xun.serialization.loads(yml)
    pd.testing.assert_series_equal(loaded, series)


def test_pandas_series_mean_serialization():
    mean = pd.Series(np.random.randn(10)).mean()
    yml = xun.serialization.dumps(mean)
    loaded = xun.serialization.loads(yml)
    assert loaded == mean
    assert type(loaded) == type(mean)


def test_pandas_series_datetime_index_serialization():
    date_range = pd.date_range(datetime.now(), periods=10, tz='UTC')
    index = pd.DatetimeIndex(date_range, freq=None)
    series = pd.Series(np.random.randn(10), index=index)
    yml = xun.serialization.dumps(series)
    loaded = xun.serialization.loads(yml)
    pd.testing.assert_series_equal(loaded, series)


def test_pandas_frame_serialization():
    frame = pd.DataFrame(np.random.randn(10, 3))
    yml = xun.serialization.dumps(frame)
    loaded = xun.serialization.loads(yml)
    pd.testing.assert_frame_equal(loaded, frame)


def test_numpy_serialization():
    numpy_array = np.random.randn(10, 3)
    yml = xun.serialization.dumps(numpy_array)
    loaded = xun.serialization.loads(yml)
    assert (loaded == numpy_array).all()


@pytest.mark.xfail
def test_xun_serialization():
    """
    This test is a sketch of what the feature should look like, may be faulty
    """
    class Functor(metaclass=xun.serialization.functor.IsoFunctor):
        class _Inverse(metaclass=xun.serialization.functor.IsoFunctor):
            def __call__(cls, value):
                return value / 10
            def __invert__(cls):
                return Functor
        def __call__(cls, value):
            return value * 10
        def __invert__(cls):
            return cls._Inverse

    @xun.function()
    def f(v: Functor) -> Functor:
        return v

    @xun.function()
    def g():
        return v
        with ...:
            v = f(10)

    assert run_in_process(g.blueprint()) == 10


@pytest.mark.xfail(reason='Composition not implemented')
def test_xun_serialization_composition():
    """
    This test is a sketch of what the feature should look like, may be faulty
    """
    from xun.serialization.pandas_types import SeriesFunctor
    from xun.serialization.functor import ListFunctor
    from xun.serialization.functor import GZip

    T = ListFunctor & SeriesFunctor & GZip.GZStrFunctor
    L = [pd.Series(np.random.randn(10)) for _ in range(3)]

    yml = xun.serialization.dumps(L, functor=T)
    loaded = xun.serialization.loads(yml, functor=T)
    for loaded, reference in zip(loaded, L):
        pd.testing.assert_series_equal(loaded, reference)
