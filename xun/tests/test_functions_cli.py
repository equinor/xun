from xun.functions import cli
from xun import XunSyntaxError
import pytest


module = cli.load_module('xun/tests/test_data/script.py')


def test_interpret_call():
    no_args = cli.interpret_call('f()', module)
    args_only = cli.interpret_call('f(1, 2, 3)', module)
    kwargs_only = cli.interpret_call('f(x="x", y="y", z="z")', module)
    args_kwargs = cli.interpret_call('f(1, 2, 3, x="x", y="y", z="z")', module)

    assert no_args == module.f.callnode()
    assert args_only == module.f.callnode(1, 2, 3)
    assert kwargs_only == module.f.callnode(x='x', y='y', z='z')
    assert args_kwargs == module.f.callnode(1, 2, 3, x='x', y="y", z="z")


def test_interpret_call_expression():
    call = cli.interpret_call('f(1 + 2)', module)
    assert call == module.f.callnode(3)


def test_syntax_errors():
    with pytest.raises(SyntaxError):
        cli.interpret_call('invalid code', module)

    with pytest.raises(XunSyntaxError):
        cli.interpret_call('f(); g()', module)

    with pytest.raises(XunSyntaxError):
        cli.interpret_call('for i in range(5): f(i)', module)

    with pytest.raises(XunSyntaxError):
        cli.interpret_call('1 + 1', module)

    with pytest.raises(XunSyntaxError):
        cli.interpret_call('(1 + 1)()', module)
