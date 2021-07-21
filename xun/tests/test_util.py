from .helpers import check_ast_equals
from typing import Any
from xun.functions import FunctionDescription
from xun.functions import describe
from xun.functions import func_arg_names
from xun.functions import function_ast
from xun.functions import function_source
from xun.functions.compatibility import ast
from xun.functions.util import assignment_target_introduced_names
from xun.functions.util import assignment_target_shape
from xun.functions.util import call_from_function_definition
from xun.functions.util import func_external_names
from xun.functions.util import overwrite_scope
from xun.functions.util import shape_to_ast_tuple
from xun.functions.util import strip_decorators
import astunparse


global_c = 3


def test_overwrite_scope():
    a = 1
    b = 2

    def f():
        return a + b + global_c

    g = overwrite_scope(f, globals={'global_c': 4})

    assert f() == 6
    assert g() == 7


def test_describe_function():
    some_value = None

    def f(a, b, c) -> Any:
        """hello world"""
        return some_value

    expected = FunctionDescription(
        src=function_source(f),
        ast=function_ast(f),
        name='f',
        qualname='test_describe_function.<locals>.f',
        doc='hello world',
        annotations={'return': Any},
        defaults=f.__defaults__,
        globals={'some_value': None},
        referenced_modules=frozenset(),
        module=f.__module__,
    )
    decomposed = describe(f)

    assert (astunparse.dump(expected.ast) ==
            astunparse.dump(decomposed.ast))
    assert (expected._replace(ast=None) ==
            decomposed._replace(ast=None))


def test_argnames():
    def argnames(f):
        fdef = function_ast(f).body[0]
        return func_arg_names(fdef)

    def no_args():
        pass

    def args_only(a, b, c):
        pass

    def kwargs_only(x="x", y="y", z="z"):
        pass

    def args_kwargs(a, b, c, x="x", y="y", z="z"):
        pass

    def full(a, b, c, *vararg, x="x", y="y", z="z", **kwarg):
        pass

    assert argnames(no_args) == frozenset()
    assert argnames(args_only) == frozenset(('a', 'b', 'c'))
    assert argnames(kwargs_only) == frozenset(('x', 'y', 'z'))
    assert argnames(args_kwargs) == frozenset(('a', 'b', 'c', 'x', 'y', 'z'))
    assert argnames(full) == frozenset(
        ('a', 'b', 'c', 'x', 'y', 'z', 'vararg', 'kwarg')
    )


def test_func_external_references():
    shadowed_external = None
    default = None

    def f(local_a, local_b=default):
        import xun
        a = external_func(external_value)
        b = xun.some_hypothetical_function(local_a, local_b)
        for shadowed_external in external_name:
            c = shadowed_external
            print(a, b, c, shadowed_external)
            print(local_a, local_b)
        return external_result

    tree = function_ast(f)
    func = tree.body[0]

    expected = frozenset({
        'external_func',
        'external_name',
        'external_result',
        'external_value',
        'print',
    })
    external_names = func_external_names(func)
    assert external_names == expected


def test_func_external_references_tuple_unpacking():
    def f():
        (a, b), c = v

    tree = function_ast(f)
    tree = strip_decorators(tree)

    expected = frozenset({'v'})
    external_names = func_external_names(tree.body[0])
    assert external_names == expected


def test_assignment_target_shape():
    target = ast.parse('a, b, c = f()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == (3, )

    target = ast.parse('a, (b,c) = f()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == (1, (2,))

    target = ast.parse('a, b, (c, d) = f()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == (2, (2,))

    target = ast.parse('(a, b), (c, d) = f()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == ((2,), (2,))

    target = ast.parse('a, (b, c, (d, e)), f = f()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == (1, (2, (2,)), 1)

    target = ast.parse('a, ((b,c,d), (e,f)), g = f()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == (1, ((3,), (2,)), 1)


def test_assignment_starred_target_shape():
    target = ast.parse('a, *bc = f()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == (1, Ellipsis)

    target = ast.parse('a, b, c, *de, f = g()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == (3, Ellipsis, 1)

    target = ast.parse('a, (b, *cd), e, f = g()').body[0].targets[0]
    shape = assignment_target_shape(target)
    assert shape == (1, (1, Ellipsis), 2)


def test_shape_to_ast_tuple():
    shape = (3,)
    ast_tuple = shape_to_ast_tuple(shape)
    expected_ast = ast.Tuple(
        elts=[ast.Constant(value=3, kind=None)],
        ctx=ast.Load(),
    )
    ok, diff = check_ast_equals(ast_tuple, expected_ast)
    assert ok, diff

    shape = (1, (2, (2,)), 1)
    ast_tuple = shape_to_ast_tuple(shape)
    expected_ast = ast.Tuple(
        elts=[
            ast.Constant(value=1, kind=None),
            ast.Tuple(
                elts=[
                    ast.Constant(value=2, kind=None),
                    ast.Tuple(
                        elts=[ast.Constant(value=2, kind=None)],
                        ctx=ast.Load(),
                    ),
                ],
                ctx=ast.Load(),
            ),
            ast.Constant(value=1, kind=None),
        ],
        ctx=ast.Load(),
    )
    ok, diff = check_ast_equals(ast_tuple, expected_ast)
    assert ok, diff


def test_starred_shape_to_ast_tuple():
    shape = (1, 1, Ellipsis)
    ast_tuple = shape_to_ast_tuple(shape)
    expected_ast = ast.Tuple(
        elts=[
            ast.Constant(value=1, kind=None),
            ast.Constant(value=1, kind=None),
            ast.Constant(value=Ellipsis, kind=None),
        ],
        ctx=ast.Load(),
    )
    ok, diff = check_ast_equals(ast_tuple, expected_ast)
    assert ok, diff


def test_assignment_target_introduced_names():
    @function_ast
    def _():
        a = 0
        b, c, *xs = 1, 2, 3, 4
        [d, e] = 3, 4
        f = g = 5
        h, I.attr, L[0] = 6
    stmts = _.body[0].body

    assert assignment_target_introduced_names(stmts[0]) == {'a'}
    assert assignment_target_introduced_names(stmts[1]) == {'b', 'c', 'xs'}
    assert assignment_target_introduced_names(stmts[2]) == {'d', 'e'}
    assert assignment_target_introduced_names(stmts[3]) == {'f', 'g'}
    assert assignment_target_introduced_names(stmts[4]) == {'h'}


def test_call_from_function_definition():
    # Simple example
    f_def = ast.parse('def f(a, b=1, *args, **kwargs): pass').body[0]
    expected_call = ast.parse('f(a, b, *args, **kwargs)').body[0].value
    generated_call = call_from_function_definition(f_def)

    ok, diff = check_ast_equals(generated_call, expected_call)
    assert ok, diff

    # Advanced example
    f_def = ast.parse(
        'def f(a, b, c, d=2, *, e=3, **my_kwargs): pass'
    ).body[0]
    expected_call = ast.parse('f(a, b, c, d, e, **my_kwargs)').body[0].value
    generated_call = call_from_function_definition(f_def)

    ok, diff = check_ast_equals(generated_call, expected_call)
    assert ok, diff
