import astunparse
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


def test_FunctionImage():
    def f(a):
        return a + d
        with ...:
            d = a + b
            b = 1
    g = xun.functions.FunctionImage(f)
    h = g.update([], {'a': 1, 'b': 2})
    i = h.update(['a'], {})

    assert h.a == 1
    assert h.b == 2
    assert i.b == 2

    with pytest.raises(AttributeError):
        g.a = 1
    with pytest.raises(AttributeError):
        _ = g.a
    with pytest.raises(AttributeError):
        _ = i.a


def test_function_compilation():
    def f():
        return global_c
        return 7

    g_img = xun.functions.FunctionImage(f)
    g = g_img.assemble(g_img.ast).compile()
    assert g() == f() and g() == global_c

    new_nodes = g_img.ast[1:]
    h_img = g_img.update(['ast'], {'cropped_ast': new_nodes})
    h = h_img.assemble(h_img.cropped_ast).compile()
    assert h() == 7

    # g shohuld not have changed
    g = g_img.assemble(g_img.ast).compile()
    assert g() == f() and g() == global_c


def test_describe_function():
    def f(a, b, c):
        pass

    expected = xun.functions.FunctionInfo(
        ast=xun.functions.function_ast(f).body[0],
        name='f',
        defaults=f.__defaults__,
        globals=f.__globals__,
        module=f.__module__,
    )
    decomposed = xun.functions.describe(f)

    assert (astunparse.dump(expected.ast) ==
            astunparse.dump(decomposed.ast))
    assert (expected._replace(ast=None) ==
            decomposed._replace(ast=None))
