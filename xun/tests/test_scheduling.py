from math import atan2
from math import radians
from math import sin
from xun.functions import CallNode, SentinelNode, TargetNode
import ast
import pickle
import pytest
import networkx as nx
import xun


def create_context():
    return xun.context(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

def sample_sin_context():
    context = create_context()

    @context.function()
    def mksample(i, step_size):
        return i / step_size

    @context.function()
    def deg_to_rad(deg):
        return radians(deg)

    @context.function()
    def sample_sin(offset, sample_count, step_size):
        return [sin(s) + offset for s in radians]
        with ...:
            samples = [mksample(i, step_size) for i in range(sample_count)]
            radians = [deg_to_rad(s) for s in samples]

    return context


def test_build_function_graph():
    context = create_context()

    @context.function()
    def sign(msg, signed='pytest'):
        pass

    @context.function()
    def message(num):
        pass

    @context.function()
    def messages(msg_count):
        with ...:
            signed = [sign(m) for m in messages]
            messages = [message(i) for i in range(msg_count)]

    call = CallNode('messages', 3)
    G, dependencies = xun.functions.build_function_graph(context, call)

    expected_dependencies = (
        CallNode('message', 0),
        CallNode('message', 1),
        CallNode('message', 2),
        CallNode('sign', SentinelNode(CallNode('message', 0))),
        CallNode('sign', SentinelNode(CallNode('message', 1))),
        CallNode('sign', SentinelNode(CallNode('message', 2))),
    )
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

    assert dependencies == expected_dependencies
    assert set(G.edges) == set(expected.edges)
    assert nx.is_isomorphic(
        G,
        expected,
        node_match=lambda a, b: a == b,
        edge_match=lambda a, b: a == b,
    )



def test_program_graph():
    context = create_context()

    @context.function()
    def start():
        return 2

    @context.function()
    def a():
        return ['a'] * repetitions
        with ...:
            repetitions = start()

    @context.function()
    def b():
        return ['b'] * repetitions
        with ...:
            repetitions = start()

    @context.function()
    def c():
        return ['c'] * repetitions
        with ...:
            repetitions = start()

    @context.function()
    def end():
        return _a + _b + _c
        with ...:
            _a = a()
            _b = b()
            _c = c()

    end_node = CallNode('end')
    call_graph = xun.functions.build_call_graph(context, end_node)

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

    assert nx.is_directed_acyclic_graph(call_graph)
    assert set(call_graph.edges) == set(reference_graph.edges)
    assert nx.is_isomorphic(
        call_graph,
        reference_graph,
        node_match=lambda a, b: a == b,
        edge_match=lambda a, b: a == b,
    )


def test_program():
    context = sample_sin_context()

    offset = 0
    sample_count = 10
    step_size = 36
    program = context.sample_sin.compile(offset, sample_count, step_size)
    result = program()

    assert result == [
        sin(radians(i / step_size)) + offset for i in range(sample_count)
    ]


def test_program_is_pickleable():
    context = sample_sin_context()

    offset = 0
    sample_count = 10
    step_size = 36
    program = context.sample_sin.compile(offset, sample_count, step_size)

    pickled_program = pickle.dumps(program)
    unpickled_program = pickle.loads(pickled_program)

    result = unpickled_program()

    assert result == [
        sin(radians(i / step_size)) + offset for i in range(sample_count)
    ]
