from immutables import Map as frozenmap
import numpy as np
import os
import pandas as pd
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
