from .helpers import PickleDriver
from math import atan2
from math import radians
from math import sin
from xun.functions import CallNode, SentinelNode, TargetNode
import ast
import pickle
import pytest
import networkx as nx
import xun


def test_functions():
    from .reference import decending_fibonacci

    blueprint = decending_fibonacci.blueprint(6)
    result = blueprint.run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    expected = [5, 3, 2, 1, 1, 0]
    assert result == expected


def test_build_function_graph():
    @xun.function()
    def sign(msg, signed='pytest'):
        pass

    @xun.function()
    def message(num):
        pass

    @xun.function()
    def messages(msg_count):
        with ...:
            signed = [sign(m) for m in messages]
            messages = [message(i) for i in range(msg_count)]

    call = CallNode('messages', 3)
    bp = messages.blueprint(3)

    expected = nx.DiGraph([
        (
            CallNode('message', 0),
            TargetNode('messages', call)
        ),
        (
            CallNode('message', 1),
            TargetNode('messages', call)
        ),
        (
            CallNode('message', 2),
            TargetNode('messages', call)
        ),
        (
            TargetNode('messages', call),
            CallNode('sign', SentinelNode(CallNode('message', 0)))
        ),
        (
            TargetNode('messages', call),
            CallNode('sign', SentinelNode(CallNode('message', 1)))
        ),
        (
            TargetNode('messages', call),
            CallNode('sign', SentinelNode(CallNode('message', 2)))
        ),
        (
            CallNode('sign', SentinelNode(CallNode('message', 0))),
            TargetNode('signed', call)
        ),
        (
            CallNode('sign', SentinelNode(CallNode('message', 1))),
            TargetNode('signed', call)
        ),
        (
            CallNode('sign', SentinelNode(CallNode('message', 2))),
            TargetNode('signed', call)
        ),
        (
            TargetNode('signed', call),
            call,
        ),
    ])

    assert set(bp.graph.edges) == set(expected.edges)
    assert nx.is_isomorphic(
        bp.graph,
        expected,
        node_match=lambda a, b: a == b,
        edge_match=lambda a, b: a == b,
    )


def test_program_graph():
    @xun.function()
    def start():
        return 2

    @xun.function()
    def a():
        return ['a'] * repetitions
        with ...:
            repetitions = start()

    @xun.function()
    def b():
        return ['b'] * repetitions
        with ...:
            repetitions = start()

    @xun.function()
    def c():
        return ['c'] * repetitions
        with ...:
            repetitions = start()

    @xun.function()
    def end():
        return _a + _b + _c
        with ...:
            _a = a()
            _b = b()
            _c = c()

    end_node = CallNode('end')
    bp = end.blueprint()

    start_node = CallNode('start')
    a_node = CallNode('a')
    b_node = CallNode('b')
    c_node = CallNode('c')

    reference_graph = nx.DiGraph([
        (start_node, TargetNode('repetitions', a_node)),
        (start_node, TargetNode('repetitions', b_node)),
        (start_node, TargetNode('repetitions', c_node)),
        (TargetNode('repetitions', a_node), a_node),
        (TargetNode('repetitions', b_node), b_node),
        (TargetNode('repetitions', c_node), c_node),
        (a_node, TargetNode('_a', end_node)),
        (b_node, TargetNode('_b', end_node)),
        (c_node, TargetNode('_c', end_node)),
        (TargetNode('_a', end_node), end_node),
        (TargetNode('_b', end_node), end_node),
        (TargetNode('_c', end_node), end_node),
    ])

    assert nx.is_directed_acyclic_graph(bp.graph)
    assert set(bp.graph.edges) == set(reference_graph.edges)
    assert nx.is_isomorphic(
        bp.graph,
        reference_graph,
        node_match=lambda a, b: a == b,
        edge_match=lambda a, b: a == b,
    )


def test_program():
    offset = 42
    sample_count = 10
    step_size = 36

    blueprint = sample_sin_blueprint(offset, sample_count, step_size)
    result = blueprint.run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    assert result == [
        sin(radians(i / step_size)) + offset for i in range(sample_count)
    ]


def test_program_is_pickleable():
    offset = 42
    sample_count = 10
    step_size = 36

    blueprint = sample_sin_blueprint(offset, sample_count, step_size)
    result = blueprint.run(
        driver=PickleDriver(),
        store=xun.functions.store.Memory(),
    )

    assert result == [
        sin(radians(i / step_size)) + offset for i in range(sample_count)
    ]


def test_function_closures_available():
    a = 11 # Closure variable

    @xun.function()
    def f():
        return a

    result = f.blueprint().run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    assert result == a


def sample_sin_blueprint(offset, sample_count, step_size):
    @xun.function()
    def mksample(i, step_size):
        return i / step_size

    @xun.function()
    def deg_to_rad(deg):
        return radians(deg)

    @xun.function()
    def sample_sin(offset, sample_count, step_size):
        return [sin(s) + offset for s in radians]
        with ...:
            samples = [mksample(i, step_size) for i in range(sample_count)]
            radians = [deg_to_rad(s) for s in samples]

    return sample_sin.blueprint(offset, sample_count, step_size)
