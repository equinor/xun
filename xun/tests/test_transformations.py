from .helpers import compare_ast
from typing import List
import ast
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
            from xun.functions import FutureValueNode as _xun_FutureValueNode
            a = _xun_FutureValueNode(_xun_CallNode('f'))
            b = _xun_FutureValueNode(_xun_CallNode('f', a))
            c = _xun_FutureValueNode(_xun_CallNode('f', b))
            return (
                _xun_store[_xun_FutureValueNode(_xun_CallNode('f'))],
                _xun_store[_xun_FutureValueNode(_xun_CallNode('f', b))],
            )
        a, c = _xun_load_constants()
        value = a + c
        return value

    known_functions = {'f'}
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

    known_functions = {'f'}
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
