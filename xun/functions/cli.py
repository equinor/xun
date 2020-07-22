from pathlib import Path
import ast
import importlib
import inspect
import networkx as nx
import xun


def xun_graph(args):
    """
    CLI entrypoint for ``xun graph`` command
    """
    import matplotlib.pyplot as plt

    call = interpret_call(args.call_string)
    script = Script(args.program)

    program = (script
        .context
        .entry(call.function_name)
        .compile(*call.args, **call.kwargs)
    )

    nx.draw_spring(program.graph, with_labels=True)
    plt.show()


def xun_exec(args):
    """
    CLI entrypoint for ``xun graph`` command
    """
    call = interpret_call(args.call_string)
    script = Script(args.program)
    script.exec(call)

class Script:
    """Script

    Attributes
    ----------
    module : module
        The context module to be executed
    context : xun.context
        The context to be executed

    Methods
    -------
    exec(call)
        Build and run program with the provided call from the context

    """
    def __init__(self, path):
        self.module = load_module(path)
        self.context = identify_context(self.module)

    def exec(self, call):
        program = (self
            .context
            .entry(call.function_name)
            .compile(*call.args, **call.kwargs)
        )
        return program()


def load_module(path):
    """Load Module

    Load and return module

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the python file to load

    Returns
    -------
    module
        The loaded module
    """
    path = Path(path).resolve()
    spec = importlib.util.spec_from_file_location('_xun_script_module', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identify_context(module):
    """Identify context

    Given a module, extract the context object from it

    Parameters
    ----------
    module : module
        xun project module

    Returns
    -------
    xun.context
        The context specified in the module
    """
    found = inspect.getmembers(module, lambda m: isinstance(m, xun.context))
    if len(found) == 0:
        raise xun.function.ContextError('No context found')
    if len(found) > 1:
        raise xun.function.ContextError('Multiple contexts found')
    return found[0][1]


def interpret_call(call_string):
    """Interpret call

    Given a call string, return a call node representing the call

    Parameters
    ----------
    call_string : str
        The call string in python syntax

    Returns
    -------
    xun.functions.CallNode
        Call node representing the call

    Examples
    --------

    >>> call_string = 'some_function(1, 2, kw=3)'
    >>> interpret_call(call_string)
    CallNode<some_function(1, 2, kw=3)>

    """
    tree = ast.parse(call_string)
    if not len(tree.body) == 1:
        raise SyntaxError('More than one statement in call string')

    expr = tree.body[0]
    if not isinstance(expr, ast.Expr):
        raise SyntaxError('Call string must be a single expression')

    call = expr.value
    if not isinstance(call, ast.Call):
        raise SyntaxError('Call string is not a call')
    if not isinstance(call.func, ast.Name):
        raise SyntaxError('Call must be to a named function')

    keywords = {ast.Constant(value=kw.arg): kw.value for kw in call.keywords}

    module = ast.fix_missing_locations(ast.Module(
        type_ignores=[],
        body=[
            ast.Assign(
                targets=[ast.Name(id='function_name', ctx=ast.Store())],
                value=ast.Constant(value=call.func.id),
            ),
            ast.Assign(
                targets=[ast.Name(id='args', ctx=ast.Store())],
                value=ast.List(elts=call.args, ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id='kwargs', ctx=ast.Store())],
                value=ast.Dict(
                    keys=list(keywords.keys()),
                    values=list(keywords.values()),
                ),
            ),
        ],
    ))

    code = compile(module, '<ast>', 'exec')

    scope = {}
    exec(code, scope)

    return xun.functions.CallNode(
        scope['function_name'],
        *scope['args'],
        **scope['kwargs'],
    )
