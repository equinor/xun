from .helpers import compare_ast
from typing import List
from xun.functions.compatibility import ast
import astor
import pytest
import networkx as nx
import xun


global_c = 3


def has_side_effect(L: List[int], kw=None):
    L[0] += 1
    if kw is not None:
        L[0] += kw
    return 42 + L[0]


def as_callable_python(func):
    fcode = (xun.functions.FunctionDecomposition(func)
        .apply(xun.functions.separate_constants)
        .apply(xun.functions.sort_constants)
        .apply(xun.functions.copy_only_constants))
    f = fcode.assemble(fcode.copy_only_constants, fcode.body)

    return f.compile()


def test_statement_dag():
    def f(b):
        return d
        with ...:
            d = a + b + global_c
            a = 7

    ln = [
        'd = a + b + global_c',
        'a = 7',
    ]
    reference_graph = nx.DiGraph([
        (ln[1], 'a'),
        ('a', ln[0]),
        ('b', ln[0]),
        ('global_c', ln[0]),
        (ln[0], 'd')
    ])

    fcode = xun.functions.FunctionDecomposition(f)
    fcode = fcode.apply(xun.functions.separate_constants)

    constant_graph = xun.functions.stmt_dag(fcode.constants)

    # Relabel nodes to their original source code, as ast.AST cannot be compared
    mapping = {
        node: astor.to_source(node).strip()
        for node in constant_graph.nodes
        if isinstance(node, ast.AST)
    }
    relabeled = nx.relabel_nodes(constant_graph, mapping)

    assert nx.is_directed_acyclic_graph(constant_graph)
    assert nx.is_directed_acyclic_graph(relabeled)
    assert nx.is_isomorphic(
        relabeled,
        reference_graph,
        node_match=lambda a, b: a == b,
        edge_match=lambda a, b: a == b,
    )


def test_fail_when_with_constant_statement_is_not_a_dag():
    def f(b):
        return d
        with ...:
            d = a + b
            a = b
            b = a # Loop

    with pytest.raises(xun.functions.NotDAGError):
        fcode = xun.functions.FunctionDecomposition(f)


def test_with_constants():
    def f():
        return d
        with ...:
            d = a + b + global_c
            a = 7
            b = 13

    g = as_callable_python(f)
    assert g() == 23 # 7 + 13 + 3


def test_with_constants_no_side_effects():
    def f():
        return L[0] + a
        with ...:
            a = has_side_effect(L, kw=5) # 42 + (L[0] + 1 + 5)
            L = [1, 2]

    g = as_callable_python(f)

    # No side effects of functions should leak into the with constants statement
    # L[0] should be 1 inside the function (after the call to has_side_effect)
    # has_side_effect adds 42 to the new L[0] inside has_side_effect
    # L[0] should be 7 inside has_side_effect
    assert g() == 1 + 42 + 7


def test_load_from_store_transformation():
    def g():
        with ...:
            a = f()
            b = f(a)
            c = f(b)
        value = a + c
        return value

    desc = xun.describe(g)

    @xun.function_ast
    def reference_source():
        def _xun_load_constants():
            from copy import deepcopy  # noqa: F401
            from xun.functions import CallNode as _xun_CallNode
            from xun.functions.store import StoreAccessor as _xun_StoreAccessor
            _xun_store_accessor = _xun_StoreAccessor(_xun_store)
            a = _xun_CallNode('f')
            b = _xun_CallNode('f', a)
            c = _xun_CallNode('f', b)
            return (
                _xun_store_accessor.load_result(_xun_CallNode('f')),
                _xun_store_accessor.load_result(_xun_CallNode('f', b)),
            )
        a, c = _xun_load_constants()
        value = a + c
        return value

    # Dummy dependency
    @xun.function()
    def dummy():
        pass
    known_functions = {'f': dummy}

    code = (xun.functions.FunctionDecomposition(desc)
        .apply(xun.functions.separate_constants)
        .apply(xun.functions.sort_constants)
        .apply(xun.functions.copy_only_constants, known_functions)
        .apply(xun.functions.load_from_store, known_functions))

    generated = [*code.load_from_store, *code.body]
    reference = reference_source.body[0].body

    for a, b in zip(generated, reference):
        if not compare_ast(a, b):
            raise ValueError('\n{} != \n{}'.format(ast.dump(a), ast.dump(b)))


def test_load_from_store_skip_if_unecessary():
    def g(a, b):
        value = a + b
        return value

    desc = xun.describe(g)

    @xun.function_ast
    def reference_source():
        value = a + b
        return value

    # Dummy dependency
    @xun.function()
    def dummy():
        pass
    known_functions = {'f': dummy}

    code = (xun.functions.FunctionDecomposition(desc)
        .apply(xun.functions.separate_constants)
        .apply(xun.functions.sort_constants)
        .apply(xun.functions.copy_only_constants, known_functions)
        .apply(xun.functions.load_from_store, known_functions))

    generated = [*code.load_from_store, *code.body]
    reference = reference_source.body[0].body

    for a, b in zip(generated, reference):
        if not compare_ast(a, b):
            raise ValueError('\n{} != \n{}'.format(ast.dump(a), ast.dump(b)))


def test_FunctionDecomposition():
    def f(a):
        pass

    g = xun.functions.FunctionDecomposition(f)
    h = g.update(a=1, b=2)
    k = h.update(a=3)

    assert h.a == 1
    assert h.b == 2

    assert k.a == 3
    assert k.b == 2

    # g is Immutable
    with pytest.raises(AttributeError):
        g.a = 1

    # existing keys are immutable
    with pytest.raises(AttributeError):
        h.a = 1


def test_FunctionDecomposition_compilation():
    def f():
        return global_c
        return 7

    g_img = xun.functions.FunctionDecomposition(f)
    g = g_img.assemble(g_img.ast.body[0].body).compile()
    assert g() == f() and g() == global_c

    new_nodes = g_img.ast.body[0].body[1:]
    h_img = g_img.update(cropped_ast=new_nodes)
    h = h_img.assemble(h_img.cropped_ast).compile()
    assert h() == 7

    # g shohuld not have changed
    g = g_img.assemble(g_img.ast.body[0].body).compile()
    assert g() == f() and g() == global_c


def test_dependency_without_target():
    @xun.function()
    def procedure():
        pass

    @xun.function()
    def workflow():
        with ...:
            procedure()
        return 1

    assert 'procedure' in workflow.dependencies

    result = workflow.blueprint().run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )
    assert result == 1


def test_xun_function_to_source():
    @xun.function()
    def f(a='a'):
        return a*2

    @xun.function()
    def g():
        with ...:
            a = f()
            b = f(a)
            c = f(b)
        value = a + c
        return value

    tree = g.callable().tree
    assert isinstance(astor.to_source(tree), str)


def test_structured_unpacking_transformation():
    def g():
        return a * x * y * z * 𝛂 * β * b + something
        with ...:
            a, ((x, y, z), (𝛂, β)), b = f()
            something = h(x, y, z)

    desc = xun.describe(g)

    @xun.function_ast
    def reference_source():
        def _xun_load_constants():
            from copy import deepcopy  # noqa: F401
            from xun.functions import CallNode as _xun_CallNode
            from xun.functions.store import StoreAccessor as _xun_StoreAccessor
            _xun_store_accessor = _xun_StoreAccessor(_xun_store)
            a, ((x, y, z), (𝛂, β)), b = _xun_CallNode('f').unpack((1, ((3,), (2,)), 1))
            something = _xun_CallNode('h', x, y, z)
            return (_xun_store_accessor.load_result(_xun_CallNode('f')),
                    _xun_store_accessor.load_result(_xun_CallNode('h', x, y, z)))
        (a, ((x, y, z), (𝛂, β)), b), something = _xun_load_constants()
        return a * x * y * z * 𝛂 * β * b + something

    # Dummy dependency
    @xun.function()
    def dummy():
        pass
    known_functions = {'f': dummy, 'h': dummy}

    code = (xun.functions.FunctionDecomposition(desc)
        .apply(xun.functions.separate_constants)
        .apply(xun.functions.sort_constants)
        .apply(xun.functions.copy_only_constants, known_functions)
        .apply(xun.functions.load_from_store, known_functions))

    generated = [*code.load_from_store, *code.body]
    reference = reference_source.body[0].body

    for a, b in zip(generated, reference):
        if not compare_ast(a, b):
            raise ValueError('\n{} != \n{}'.format(ast.dump(a), ast.dump(b)))
