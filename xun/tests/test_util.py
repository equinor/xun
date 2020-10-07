import ast
import astunparse
import xun


global_c = 3


def test_overwrite_scope():
    a = 1
    b = 2

    def f():
        return a + b + global_c

    g = xun.functions.util.overwrite_scope(f, globals={'global_c': 4})

    assert f() == 6
    assert g() == 7


def test_describe_function():
    some_value = None
    def f(a, b, c):
        return some_value

    expected = xun.functions.FunctionDescription(
        src=xun.functions.function_source(f),
        ast=xun.functions.function_ast(f),
        name='f',
        defaults=f.__defaults__,
        globals={'some_value': None},
        referenced_modules=frozenset(),
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
        return xun.functions.func_arg_names(fdef)

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


def test_func_external_references_tuple_unpacking():
    def f():
        (a, b), c = v

    tree = xun.functions.function_ast(f)
    tree = xun.functions.strip_decorators(tree)

    expected = frozenset({'v'})
    external_names = xun.functions.func_external_names(tree.body[0])
    assert external_names == expected


def test_targets_in_tuple():
    tree_of_tuples = ast.parse('(a, b), c, (d,)').body[0].value
    targets = xun.functions.util.targets_in_tuple(tree_of_tuples)

    assert targets == ['a', 'b', 'c', 'd']
