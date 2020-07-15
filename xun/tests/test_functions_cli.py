from xun.functions import CallNode
from xun.functions import driver
from xun.functions import store
from xun.functions import cli
import xun


def test_Script():
    s = cli.Script('xun/tests/test_data/script.py')

    assert isinstance(s.context, xun.context)
    assert isinstance(s.context.driver, driver.Local)
    assert isinstance(s.context.store, store.Memory)
    assert tuple(s.context.functions.keys()) == ('hello', 'hello_world')

    call = CallNode('hello_world', 'world')
    result = s.exec(call)
    assert result == 'hello world!'


def test_interpret_call():
    no_args = cli.interpret_call('f()')
    args_only = cli.interpret_call('f(1, 2, 3)')
    kwargs_only = cli.interpret_call('f(x="x", y="y", z="z")')
    args_kwargs = cli.interpret_call('f(1, 2, 3, x="x", y="y", z="z")')

    assert no_args == CallNode('f')
    assert args_only == CallNode('f', 1, 2, 3)
    assert kwargs_only == CallNode('f', x='x', y='y', z='z')
    assert args_kwargs == CallNode('f', 1, 2, 3, x='x', y="y", z="z")
