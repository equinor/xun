from .helpers import check_ast_equals
from .helpers import run_in_process
from typing import List
from xun.functions import transformations as xform
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
    desc = xun.functions.describe(func)
    body, constants = xform.separate_constants(desc)
    sorted_constants, _ = xform.sort_constants(constants)
    copy_only_constants = xform.copy_only_constants(sorted_constants)
    f = xform.assemble(desc, copy_only_constants, body)

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

    fdesc = xun.functions.describe(f)
    _, constants = xform.separate_constants(fdesc)

    constant_graph = xun.functions.stmt_dag(constants)

    # Relabel nodes to their original source code, as ast.AST cannot be
    # compared
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
            b = a  # Loop

    with pytest.raises(xun.functions.NotDAGError):
        xun.functions.describe(f)


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
    def func():
        with ...:
            a = f()
            b = h(a)
            c = g(b)
        value = a + c
        return value

    desc = xun.describe(func)

    @xun.function_ast
    def reference_source():
        def _xun_load_constants():
            from xun.functions import unpack as _xun_unpack
            from copy import deepcopy as _xun_deepcopy  # noqa: F401
            from xun.functions import CallNode as _xun_CallNode
            from xun.functions.store import StoreAccessor as _xun_StoreAccessor
            _xun_store_accessor = _xun_StoreAccessor(_xun_store)
            a = _xun_CallNode('f', 'K9ZuxDD5x6atLkNd')
            b = _xun_CallNode('h', 'K9ZuxDD5x6atLkNd', a)
            c = _xun_CallNode('g', 'K9ZuxDD5x6atLkNd', b)
            return _xun_store_accessor.deepload(a, c)
        a, c = _xun_load_constants()
        value = a + c
        return value

    # Dummy dependency
    @xun.function()
    def dummy():
        pass
    known_functions = {'f': dummy, 'h': dummy, 'g': dummy}

    body, constants = xform.separate_constants(desc)
    sorted_constants, _ = xform.sort_constants(constants)
    copy_only = xform.copy_only_constants(sorted_constants, known_functions)
    unpacked = xform.unpack_unpacking_assignments(copy_only)
    load_from_store = xform.load_from_store(body, unpacked, known_functions)

    generated = [*load_from_store, *body]
    reference = reference_source.body[0].body

    ok, diff = check_ast_equals(generated, reference)
    assert ok, diff


def test_structured_unpacking_transformation():
    def g():
        with ...:
            a, b, ((x, y, z), (𝛂, β)), c, d = f()
            something = h(x, y, z)
        return a * b * x * y * z * 𝛂 * β * c * d + something

    desc = xun.describe(g)

    # Dummy dependency
    @xun.function()
    def dummy():
        pass
    known_functions = {'f': dummy, 'h': dummy}

    body, constants = xform.separate_constants(desc)
    sorted_constants, _ = xform.sort_constants(constants)
    copy_only = xform.copy_only_constants(sorted_constants, known_functions)
    unpacked = xform.unpack_unpacking_assignments(copy_only)
    load_from_store = xform.load_from_store(body, unpacked, known_functions)

    @xun.function_ast
    def reference_source():
        def _xun_load_constants():
            from xun.functions import unpack as _xun_unpack
            from copy import deepcopy as _xun_deepcopy  # noqa: F401
            from xun.functions import CallNode as _xun_CallNode
            from xun.functions.store import StoreAccessor as _xun_StoreAccessor
            _xun_store_accessor = _xun_StoreAccessor(_xun_store)
            a, b, ((x, y, z), (𝛂, β)), c, d = _xun_unpack(
                (2, ((3,), (2,)), 2),
                _xun_CallNode('f', 'K9ZuxDD5x6atLkNd')
            )
            something = _xun_CallNode('h', 'K9ZuxDD5x6atLkNd', x, y, z)
            return _xun_store_accessor.deepload(
                a, b, c, d, something, x, y, z, α, β
            )
        a, b, c, d, something, x, y, z, α, β = _xun_load_constants()
        return a * b * x * y * z * 𝛂 * β * c * d + something

    generated = [*load_from_store, *body]
    reference = reference_source.body[0].body

    ok, diff = check_ast_equals(generated, reference)
    assert ok, diff


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

    body, constants = xform.separate_constants(desc)
    sorted_constants, _ = xform.sort_constants(constants)
    copy_only = xform.copy_only_constants(sorted_constants, known_functions)
    load_from_store = xform.load_from_store(body, copy_only, known_functions)

    generated = [*load_from_store, *body]
    reference = reference_source.body[0].body

    ok, diff = check_ast_equals(generated, reference)
    assert ok, diff


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

    result = run_in_process(workflow.blueprint())
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
