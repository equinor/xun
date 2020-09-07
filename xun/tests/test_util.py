import astunparse
import inspect
import pytest
import xun


global_c = 3


def test_overwrite_globals():
    a = 1
    b = 2

    def f():
        return a + b + global_c

    g = xun.functions.overwrite_globals(f, globals={'global_c': 4})

    assert f() == 6
    assert g() == 7


def test_describe_function():
    some_value = None
    def f(a, b, c):
        return some_value

    # Some value is a non-local bound value, and not a global. It has to be
    # injected into the functions globals.
    f = xun.functions.overwrite_globals(
        f,
        {
            **f.__globals__,
            'some_value': some_value,
        }
    )

    expected = xun.functions.FunctionDescription(
        src=xun.functions.function_source(f),
        ast=xun.functions.function_ast(f),
        name='f',
        defaults=f.__defaults__,
        globals={'some_value': None},
        module_infos={},
        module=f.__module__,
    )
    decomposed = xun.functions.describe(f)

    assert (astunparse.dump(expected.ast) ==
            astunparse.dump(decomposed.ast))
    assert (expected._replace(ast=None) ==
            decomposed._replace(ast=None))


def test_argnames():
    def argnames(f):
        fdef = xun.functions.function_ast(f).body[0]
        return xun.functions.argnames(fdef)

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

    tree = xun.functions.function_ast(f)
    func = tree.body[0]

    expected = frozenset({
        'external_func',
        'external_name',
        'external_result',
        'external_value',
        'print',
    })
    external_names = xun.functions.func_external_names(func)
    assert external_names == expected
