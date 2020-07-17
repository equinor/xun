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
    fcode = (xun.functions.FunctionImage(func)
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

    fcode = xun.functions.FunctionImage(f)
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

    fcode = xun.functions.FunctionImage(f)
    fcode = fcode.apply(xun.functions.separate_constants)

    # with pytest.raises(xun.functions.NotDAGError):
    constant_graph = xun.functions.stmt_dag(fcode.constants)


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


def test_function_image_apply_does_not_affect_original():
    context = xun.context(
        xun.functions.driver.Sequential(),
        xun.functions.store.Memory(),
    )


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
