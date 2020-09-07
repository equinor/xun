from xun.functions import CallNode
from xun.functions import driver
from xun.functions import store
from xun.functions import cli
import xun


def test_interpret_call():
    no_args = cli.interpret_call('f()')
    args_only = cli.interpret_call('f(1, 2, 3)')
    kwargs_only = cli.interpret_call('f(x="x", y="y", z="z")')
    args_kwargs = cli.interpret_call('f(1, 2, 3, x="x", y="y", z="z")')

    assert no_args == CallNode('f')
    assert args_only == CallNode('f', 1, 2, 3)
    assert kwargs_only == CallNode('f', x='x', y='y', z='z')
    assert args_kwargs == CallNode('f', 1, 2, 3, x='x', y="y", z="z")
