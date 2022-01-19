from contextlib import contextmanager
from hypothesis import given
from hypothesis import settings
from hypothesis import Phase
from hypothesis.strategies import builds
from hypothesis.strategies import dictionaries
from hypothesis.strategies import lists
from hypothesis.strategies import sampled_from
from hypothesis.strategies import text
from hypothesis.strategies import tuples
from string import ascii_lowercase
from types import SimpleNamespace
from xun.functions import CopyError
import base64
import contextlib
import copy
import operator
import os
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
def Layered():
    with create_instance(TmpDisk) as store:
        yield xun.functions.store.Layered(
            xun.functions.store.Memory(),
            store,
        )


# Stores to test
stores = [
    Memory,
    TmpDisk,
    Layered,
]


def b64hash():
    return base64.urlsafe_b64encode(os.urandom(32))


values = sampled_from([0, 1, 1.1, 0.0, 'Hello World', b'hello world'])
names = text(
    alphabet=ascii_lowercase + '_',
    min_size=1,
    max_size=5)
args = lists(values, max_size=3)
kwargs = dictionaries(values, values, max_size=3)
callnodes = builds(
    lambda name, args, kwargs: xun.functions.CallNode(
        name, b64hash(), args, kwargs),
    names,
    args,
    kwargs,
)
tags = dictionaries(names, text(), max_size=3)
values_and_tags = tuples(values, tags)
store_contents = dictionaries(
    callnodes,
    values_and_tags,
    min_size=1,
    max_size=10
)


@contextlib.contextmanager
def create_instance(cls):
    f_hash = 'xg30cGXs0nKN8gdbzYFWMKidNySbgYZtg5dRV2bj58w='
    main_hash = 'ADdFftG12ZwLBHmkPHE9XxBzXrOgE2JSia-ES-Bp7ZM='
    f_0 = xun.functions.CallNode('f', f_hash, 0)
    f_1 = xun.functions.CallNode('f', f_hash, 1)
    f_2 = xun.functions.CallNode('f', f_hash, 2)
    f_3 = xun.functions.CallNode('f', f_hash, 3)
    f_4 = xun.functions.CallNode('f', f_hash, 4)
    main_0 = xun.functions.CallNode('main', main_hash, 0)
    main_1 = xun.functions.CallNode('main', main_hash, 1)
    callnodes = SimpleNamespace(f_0=f_0, f_1=f_1, f_2=f_2, f_3=f_3, f_4=f_4,
                                main_0=main_0, main_1=main_1)

    def tags(function_name, entry_point, day):
        return {
            'start_time': f'2030-01-{day}T13:37:00+00:00',
            'entry_point': entry_point,
            'function_name': function_name,
        }

    with cls() as inst:
        # Won't be seletect
        inst.store(f_3, 3, **tags('f', 'main', '01'))
        inst.store(f_4, 4, start_time='2030-01-03T13:37', function_name='f')

        # Will be selected
        inst.store(f_0, 0, **tags('f', 'main', '02'))
        inst.store(f_1, 1, **tags('f', 'main', '02'))
        inst.store(main_0, 1, **tags('main', 'main', '02'))

        inst.store(f_2, 1, **tags('f', 'main', '03'))
        inst.store(main_1, 1, **tags('main', 'main', '03'))
        yield inst, callnodes


@pytest.mark.parametrize('cls', stores)
@settings(phases=[Phase.generate, Phase.target, Phase.explain],
          deadline=500,
          max_examples=20)
@given(contents=store_contents)
def test_store_implementation(cls, contents):
    with cls() as store:
        for key, (value, _) in contents.items():
            store.store(key, value)
        for key, (value, _) in contents.items():
            assert key in store
            assert store[key] == value


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
@settings(phases=[Phase.generate, Phase.target, Phase.explain],
          deadline=500,
          max_examples=20)
@given(contents=store_contents)
def test_store_tags(cls, contents):
    with cls() as store:
        for key, (value, tags) in contents.items():
            store.store(key, value, **tags)
        for key, (value, tags) in contents.items():
            assert key in store
            assert store[key] == value
            assert store.tags[key] == tags


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
@pytest.mark.parametrize('op', [operator.eq,
                                operator.gt,
                                operator.ge,
                                operator.lt,
                                operator.le])
def test_store_select_operator(cls, op):
    with create_instance(cls) as (store, callnodes):
        value = '2030-01-02T13:37:00+00:00'
        expected = {
            cn for cn in callnodes.__dict__.values()
            if op(store.tags[cn]['start_time'], value)
        }

        condition = op(store.tags.start_time, value)
        result = store.select(condition)
        assert result == expected


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_store_select_shape(cls):
    with create_instance(cls) as (store, callnodes):
        result = store.select(
            store.tags.start_time > '2030-01-02',
            store.tags.entry_point,
            store.tags.function_name,
            shape={
                store.tags.start_time: {
                    store.tags.entry_point: {
                        store.tags.function_name: ...,
                    },
                },
                store.tags.entry_point: ...,
            }
        )

        assert result == {
            '2030-01-02T13:37:00+00:00': {
                'main': {
                    'f': {callnodes.f_0, callnodes.f_1},
                    'main': {callnodes.main_0},
                },
            },
            '2030-01-03T13:37:00+00:00': {
                'main': {
                    'f': {callnodes.f_2},
                    'main': {callnodes.main_1},
                },
            },
            'main': {
                callnodes.f_0,
                callnodes.f_1,
                callnodes.f_2,
                callnodes.main_0,
                callnodes.main_1,
            },
        }


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_store_query(cls):
    with create_instance(cls) as (store, callnodes):
        result = store.query('() => ...')
        assert result == {
            callnodes.f_0,
            callnodes.f_1,
            callnodes.f_2,
            callnodes.f_3,
            callnodes.f_4,
            callnodes.main_0,
            callnodes.main_1,
        }


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_store_query_argument(cls):
    with create_instance(cls) as (store, callnodes):
        result = store.query('(start_time) => start_time { ... }')
        assert result == {
            '2030-01-03T13:37': {
                callnodes.f_4,
            },
            '2030-01-01T13:37:00+00:00': {
                callnodes.f_3,
            },
            '2030-01-02T13:37:00+00:00': {
                callnodes.f_0,
                callnodes.f_1,
                callnodes.main_0,
            },
            '2030-01-03T13:37:00+00:00': {
                callnodes.f_2,
                callnodes.main_1,
            },
        }


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_store_query_advanced(cls):
    with create_instance(cls) as (store, callnodes):
        result = store.query("""
        (start_time>="2030-01-02" entry_point function_name) =>
            start_time {
                entry_point {
                    function_name {
                        ...
                    }
                }
            }
            entry_point {
                ...
            }
        """)

        assert result == {
            '2030-01-02T13:37:00+00:00': {
                'main': {
                    'f': {callnodes.f_0, callnodes.f_1},
                    'main': {callnodes.main_0},
                },
            },
            '2030-01-03T13:37:00+00:00': {
                'main': {
                    'f': {callnodes.f_2},
                    'main': {callnodes.main_1},
                },
            },
            'main': {
                callnodes.f_0,
                callnodes.f_1,
                callnodes.f_2,
                callnodes.main_0,
                callnodes.main_1,
            },
        }


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_store_remove(cls):
    with create_instance(cls) as (store, callnodes):
        store.remove(callnodes.f_2)
        assert callnodes.f_2 not in store

        # Test indented internal tag database
        result_id = callnodes.f_2.sha256(encode=False)
        results = list(store._tagdb.mem.execute('''
            SELECT deleted FROM _xun_results_table
            WHERE result_id = ?
            ORDER BY journal_id
        ''', (result_id,)))
        assert results == [(0,), (1,)]
        tags = list(store._tagdb.mem.execute('''
            SELECT deleted FROM _xun_tags_table
            WHERE result_id = ?
            ORDER BY journal_id
        ''', (result_id,)))
        assert tags == [(0,), (0,), (0,), (1,), (1,), (1,)]


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_store_missing_tags_raise(cls):
    with create_instance(cls) as (store, callnodes):
        del store[callnodes.f_0]
        with pytest.raises(KeyError):
            store.tags[callnodes.f_0]


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_store_rewrite_tags(cls):
    with create_instance(cls) as (store, callnodes):
        new_tags = {'hello': 'world'}
        store.store(callnodes.f_1, 1, **new_tags)
        assert store.tags[callnodes.f_1] == new_tags


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_tags_are_not_duplicated_on_double_write(cls):
    with create_instance(cls) as (store, callnodes):
        result_id = callnodes.f_0.sha256(encode=False)
        results = list(store._tagdb.mem.execute('''
            SELECT * FROM _xun_results_table
            WHERE result_id = ?
            ORDER BY journal_id
        ''', (result_id,)))
        tags = list(store._tagdb.mem.execute('''
            SELECT * FROM _xun_tags_table
            WHERE result_id = ?
            ORDER BY journal_id
        ''', (result_id,)))

        store.store(callnodes.f_0, 1, **store.tags[callnodes.f_0])

        results_after = list(store._tagdb.mem.execute('''
            SELECT * FROM _xun_results_table
            WHERE result_id = ?
            ORDER BY journal_id
        ''', (result_id,)))
        tags_after = list(store._tagdb.mem.execute('''
            SELECT * FROM _xun_tags_table
            WHERE result_id = ?
            ORDER BY journal_id
        ''', (result_id,)))

        assert results == results_after
        assert tags == tags_after


@pytest.mark.xfail(reason='Tagged stores not implemented')
@pytest.mark.parametrize('cls', stores)
def test_store_must_be_picklable(cls):
    if cls is Memory:
        pytest.skip('Cannot transport in-memory store')
    with create_instance(cls) as (store, callnodes):
        pickled = pickle.dumps(store)
        unpickled = pickle.loads(pickled)

        store.store(xun.functions.CallNode('f', '', 3), 3)
        assert unpickled[xun.functions.CallNode('f', '', 3)] == 3
        unpickled.store(xun.functions.CallNode('g', '', 3), 4)
        assert store[xun.functions.CallNode('g', '', 3)] == 4

        q0 = store.select(store.tags.start_time > '2030-01-02')
        q1 = unpickled.select(unpickled.tags.start_time > '2030-01-02')
        assert q0 == q1

        for callnode in vars(callnodes).values():
            assert callnode in unpickled
            assert store.tags[callnode] == unpickled.tags[callnode]


def test_memory_store_not_picklable():
    store = xun.functions.store.Memory()

    with pytest.raises(CopyError):
        copy.copy(store)
    with pytest.raises(CopyError):
        copy.deepcopy(store)
    with pytest.raises(CopyError):
        pickle.dumps(store)


def test_layered_store_writes_to_top_layer():
    with create_instance(TmpDisk) as (store, callnodes):
        mem = xun.functions.store.Memory()
        layered = xun.functions.store.Layered(
            mem,
            store,
        )
        callnode = xun.functions.CallNode('f', '', 3)
        layered.store(callnode, 3)
        assert callnode in layered
        assert callnode in mem
        assert callnode not in store
