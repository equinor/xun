from xun.functions import CallNode
from xun.functions import cli
import pytest


def test_interpret_call():
    no_args = cli.interpret_call('f()')
    args_only = cli.interpret_call('f(1, 2, 3)')
    kwargs_only = cli.interpret_call('f(x="x", y="y", z="z")')
    args_kwargs = cli.interpret_call('f(1, 2, 3, x="x", y="y", z="z")')

    assert no_args == CallNode('f')
    assert args_only == CallNode('f', 1, 2, 3)
    assert kwargs_only == CallNode('f', x='x', y='y', z='z')
    assert args_kwargs == CallNode('f', 1, 2, 3, x='x', y="y", z="z")


def test_interpret_call_expression():
    call = cli.interpret_call('f(1 + 2)')
    assert call == CallNode('f', 3)


def test_syntax_errors():
    with pytest.raises(SyntaxError):
        cli.interpret_call('invalid code')

    with pytest.raises(SyntaxError):
        cli.interpret_call('f(); g()')

    with pytest.raises(SyntaxError):
        cli.interpret_call('for i in range(5): f(i)')

    with pytest.raises(SyntaxError):
        cli.interpret_call('1 + 1')

    with pytest.raises(SyntaxError):
        cli.interpret_call('(1 + 1)()')
