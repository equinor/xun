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
    pass_by_value = xform.pass_by_value(sorted_constants)
    f = xform.assemble(desc, pass_by_value, body)

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


def test_load_constants_transformation():
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
        _xun_store_accessor = yield
        yield
        def _xun_load_constants():
            from xun.functions.runtime import load_results_by_deepcopy as _xun_load_results_by_deepcopy
            from xun.functions.runtime import unpack as _xun_unpack  # noqa: F401
            from xun.functions.runtime import pass_by_value as _xun_pass_by_value  # noqa: F401
            a = _xun_pass_by_value(f)
            b = _xun_pass_by_value(h, a)
            c = _xun_pass_by_value(g, b)
            return _xun_load_results_by_deepcopy(_xun_store_accessor, a, c)
        a, c = _xun_load_constants()
        value = a + c
        return value

    # Dummy dependency
    @xun.function()
    def dummy():
        pass
    known_functions = {'f': dummy, 'h': dummy, 'g': dummy}

    head = xform.generate_header()
    body, constants = xform.separate_constants(desc)
    sorted_constants, _ = xform.sort_constants(constants)
    copy_only = xform.pass_by_value(sorted_constants)
    unpacked = xform.unpack_unpacking_assignments(copy_only)
    load_constants = xform.load_constants(body, unpacked)

    generated = [*head, *load_constants, *body]
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

    head = xform.generate_header()
    body, constants = xform.separate_constants(desc)
    sorted_constants, _ = xform.sort_constants(constants)
    copy_only = xform.pass_by_value(sorted_constants)
    unpacked = xform.unpack_unpacking_assignments(copy_only)
    load_constants = xform.load_constants(body, unpacked)

    @xun.function_ast
    def reference_source():
        _xun_store_accessor = yield
        yield
        def _xun_load_constants():
            from xun.functions.runtime import load_results_by_deepcopy as _xun_load_results_by_deepcopy
            from xun.functions.runtime import unpack as _xun_unpack  # noqa: F401
            from xun.functions.runtime import pass_by_value as _xun_pass_by_value  # noqa: F401
            a, b, ((x, y, z), (𝛂, β)), c, d = _xun_unpack(
                (2, ((3,), (2,)), 2), _xun_pass_by_value(f)
            )
            something = _xun_pass_by_value(h, x, y, z)
            return _xun_load_results_by_deepcopy(
                _xun_store_accessor, a, b, c, d, something, x, y, z, α, β
            )
        a, b, c, d, something, x, y, z, α, β = _xun_load_constants()
        return a * b * x * y * z * 𝛂 * β * c * d + something

    generated = [*head, *load_constants, *body]
    reference = reference_source.body[0].body

    ok, diff = check_ast_equals(generated, reference)
    assert ok, diff


def test_interface_graph_transformation():
    @xun.function()
    def f(arg):
        return arg

    def g(arg):
        yield from f(arg * 2)

    desc = xun.describe(g)

    interface_call, target_call = xform.separate_interface_and_target(desc, f)
    interface = xform.build_interface_graph(interface_call, target_call)
    generated = [*interface]

    @xun.function_ast
    def reference_source(arg):
        from xun.functions.runtime import detect_dependencies_by_deepcopy as _xun_detect_dependencies_by_deepcopy
        _xun_graph = _xun_detect_dependencies_by_deepcopy(f(arg * 2))
        _xun_graph.add_edge(f(arg * 2), g(arg))
        return _xun_graph

    reference = reference_source.body[0].body

    ok, diff = check_ast_equals(generated, reference)
    assert ok, diff


def test_interface_task_transformation():
    @xun.function()
    def f(arg):
        return arg

    def g(arg):
        yield from f(arg * 2)

    desc = xun.describe(g)

    interface_call, target_call = xform.separate_interface_and_target(desc, f)
    interface = xform.interface_raise_on_execution(interface_call, target_call)
    generated = [*interface]

    @xun.function_ast
    def reference_source(arg):
        from xun.functions import XunInterfaceError as _xun_InterfaceError
        raise _xun_InterfaceError(
            f'{f(arg * 2)} did not produce a result for {g(arg)}'
        )

    reference = reference_source.body[0].body

    ok, diff = check_ast_equals(generated, reference)
    assert ok, diff


def test_load_constants_skip_if_unecessary():
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
    copy_only = xform.pass_by_value(sorted_constants)
    load_constants = xform.load_constants(body, copy_only)

    generated = [*load_constants, *body]
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

    tree = g.callable.tree
    assert isinstance(astor.to_source(tree), str)
