from .helpers import PickleDriver
from .helpers import FakeRedis
from .helpers import sample_sin_blueprint
from xun.functions import CallNode
from xun.functions import CopyError
from xun.functions import XunSyntaxError
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
            sign(message('3 messages'))
            messages = [message(i) for i in range(msg_count)]
            [sign(m) for m in messages]

    CallNode('messages', 3)
    bp = messages.blueprint(3)

    expected = nx.DiGraph([
        (
            CallNode('message', '3 messages'),
            CallNode('sign', CallNode('message', '3 messages')),
        ),
        (
            CallNode('sign', CallNode('message', '3 messages')),
            CallNode('messages', 3),
        ),
        (
            CallNode('message', 0),
            CallNode('sign', CallNode('message', 0)),
        ),
        (
            CallNode('message', 1),
            CallNode('sign', CallNode('message', 1)),
        ),
        (
            CallNode('message', 2),
            CallNode('sign', CallNode('message', 2)),
        ),
        (
            CallNode('sign', CallNode('message', 0)),
            CallNode('messages', 3),
        ),
        (
            CallNode('sign', CallNode('message', 1)),
            CallNode('messages', 3),
        ),
        (
            CallNode('sign', CallNode('message', 2)),
            CallNode('messages', 3),
        ),
    ])

    assert set(bp.graph.edges) == set(expected.edges)
    assert nx.is_isomorphic(
        bp.graph,
        expected,
        node_match=lambda a, b: a == b,
        edge_match=lambda a, b: a == b,
    )


def test_blueprint_graph():
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
        (start_node, a_node),
        (start_node, b_node),
        (start_node, c_node),
        (a_node, end_node),
        (b_node, end_node),
        (c_node, end_node),
    ])

    assert nx.is_directed_acyclic_graph(bp.graph)
    assert set(bp.graph.edges) == set(reference_graph.edges)
    assert nx.is_isomorphic(
        bp.graph,
        reference_graph,
        node_match=lambda a, b: a == b,
        edge_match=lambda a, b: a == b,
    )


def test_blueprint():
    blueprint, expected = sample_sin_blueprint()

    result = blueprint.run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    assert result == expected


def test_blueprint_is_picklable():
    blueprint, expected = sample_sin_blueprint()

    with FakeRedis() as redis:
        result = blueprint.run(
            driver=PickleDriver(),
            store=redis,
        )

    assert result == expected


def test_failure_on_use_of_unresolved_call():
    def use(value):
        return value + 1

    @xun.function()
    def f():
        pass

    @xun.function()
    def g():
        with ...:
            a = f()
            b = use(a)
        return b

    with pytest.raises(CopyError):
        g.blueprint()


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


def test_function_with_keywords():
    @xun.function()
    def f(a, b=None):
        return b if b is not None else a

    # We wrap the call to f in another xun function to ensure that it passes
    # through the transformation code.
    @xun.function()
    def g(a, b=None):
        return r
        with ...:
            r = f(a=a, b=b)

    assert g.blueprint(1).run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    ) == 1
    assert g.blueprint(1, 2).run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    ) == 2


def test_module_imports():
    import math
    import math as maths
    from math import pi

    @xun.function()
    def f():
        return maths.floor(pi) + math.floor(math.e)

    result = f.blueprint().run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    assert result == 5


def test_require_single_with_constants_statement():
    with pytest.raises(ValueError):
        @xun.function()
        def two_with_constants():
            with ...:
                pass
            with ...:
                pass


def test_fail_on_mutating_assingment():
    class MyClass:
        pass

    with pytest.raises(TypeError):
        @xun.function()
        def f():
            with ...:
                L = [1]
                L[0] = 2

    with pytest.raises(TypeError):
        @xun.function()
        def g():
            with ...:
                instance = MyClass()
                instance.field = 2


def test_structured_unpacking():
    @xun.function()
    def f():
        return ('a', 'b'), 'c'

    @xun.function()
    def g(v):
        return v * 2

    @xun.function()
    def h():
        with ...:
            (a, b), c = f()
            new_b = g(b)
        return a + new_b + c

    result = h.blueprint().run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    assert result == 'abbc'


def test_structured_unpacking_list():
    @xun.function()
    def f():
        return ('a', ('b', 'c'))

    @xun.function()
    def h():
        with ...:
            [a, [b, c]] = f()
        return a + b + c

    result = h.blueprint().run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    assert result == 'abc'


def test_nested_calls():
    @xun.function()
    def f():
        return 'a'

    @xun.function()
    def g(v, other='b'):
        return v + other

    @xun.function()
    def h():
        with ...:
            r = g(f())
            s = g(g(f()), other=f())
        return r + '_' + s

    result = h.blueprint().run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    assert result == 'ab_aba'


def test_functions_hashes():
    @xun.function()
    def f():
        pass
    @xun.function()
    def g():
        with ...:
            f()
    f0 = f.hash
    g0 = g.hash

    # redefining the same function results in the same hash
    @xun.function()
    def g():
        with ...:
            f()
    g1 = g.hash
    assert g1 == g0

    # redefining the different function with same name results in different
    # hash
    @xun.function()
    def f():
        return 0
    f1 = f.hash
    assert f0 != f1

    # redefining the same function with different dependencies results in
    # different hash
    @xun.function()
    def g():
        with ...:
            f()
    g2 = g.hash
    assert g2 != g0


def test_function_version_completeness():
    driver = xun.functions.driver.Sequential()
    store = xun.functions.store.Memory()
    accessor = xun.functions.store.StoreAccessor(store)

    @xun.function()
    def f():
        return 0
    @xun.function()
    def workflow():
        with ...:
            r = f()
        return r

    f0 = f
    w0 = workflow

    assert not accessor.completed(CallNode('f'), hash=f0.hash)
    assert not accessor.completed(CallNode('workflow'), hash=w0.hash)

    r0 = w0.blueprint().run(driver=driver, store=store)

    assert accessor.completed(CallNode('f'), hash=f0.hash)
    assert accessor.completed(CallNode('workflow'), hash=w0.hash)
    assert r0 == 0

    # Redefintion

    @xun.function()
    def f():
        return 1

    f1 = f

    w1 = xun.functions.Function(workflow.desc, {'f': f1}, None)

    assert accessor.completed(CallNode('f'), hash=f0.hash)
    assert accessor.completed(CallNode('workflow'), hash=w0.hash)
    assert not accessor.completed(CallNode('f'), hash=f1.hash)
    assert not accessor.completed(CallNode('workflow'), hash=w1.hash)

    r1 = w1.blueprint().run(driver=driver, store=store)

    assert accessor.completed(CallNode('f'), hash=f0.hash)
    assert accessor.completed(CallNode('workflow'), hash=w0.hash)
    assert accessor.completed(CallNode('f'), hash=f1.hash)
    assert accessor.completed(CallNode('workflow'), hash=w1.hash)
    assert r1 == 1

    # Rerun w0 to overwrite the latest result, this ensures that we test that
    # the correct hash is used when loading the result of f. To force a rerun
    # of w0, we scramble the hash using w1's hash (since it is suitably random)
    w0.hash = bytes(a ^ b for a, b in zip(w0.hash, w1.hash))
    r2 = w0.blueprint().run(driver=driver, store=store)
    assert r2 == 0


def test_fail_on_reasignment():
    @xun.function()
    def f():
        return 'f'

    with pytest.raises(XunSyntaxError):
        @xun.function()
        def h():
            with ...:
                f = f()
            return f


def test_empty_xun_function():
    @xun.function()
    def g():
        return 'a'

    @xun.function()
    def f():
        with ...:
            g()

    f.blueprint().run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )
