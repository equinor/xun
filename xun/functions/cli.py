from .compatibility import ast
from pathlib import Path
import importlib
import inspect
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import sys
import xun


def xun_graph(args):
    """
    CLI entrypoint for ``xun graph`` command
    """
    plt.style.use('dark_background')

    plt.style.use('dark_background')

    call = interpret_call(args.call_string)
    module = load_module(args.module)
    function = identify_function(call, module)

    blueprint = function.blueprint(*call.args, **call.kwargs)

    G = blueprint.graph

    if args.dot_layout:
        draw_dot(plt, G, call)
    elif args.dot:
        nx.nx_agraph.write_dot(G, sys.stdout)
    else: # Draw list is default behavior
        draw_list(plt, G, call)


def draw_list(plt, G, root):
    cmap = plt.get_cmap('viridis')
    colors = cmap(np.linspace(0, 1, len(G.nodes())))

    order = list(nx.topological_sort(G))
    index_of = {node: idx for idx, node in enumerate(order)}
    color_of = {node: colors[index_of[node]] for node in G.nodes()}
    colors = [colors[index_of[node]] for node in G.nodes()]

    # Layout

    top_sort_next = {
        **{
            node: top_sort_next
            for node, top_sort_next in zip(order[:-1], order[1:])
        },
        root: None
    }

    pos = {
        **{node: (0, i) for i, node in enumerate(order[:-1])},
        root: (-0.1, max(0.0, len(order) - 2))
    }
    label_pos = {
        node: (0.025, y) if node != root else (-0.125, len(order) - 1)
        for node, (x, y) in pos.items()
    }

    # Plot

    nx.draw_networkx_nodes(
        G,
        pos=pos,
        node_size=25,
        node_color=colors,
    )
    nx.draw_networkx_labels(
        nx.subgraph_view(G, filter_node=lambda node: node != root),
        pos=label_pos,
        font_size=8,
        font_color='white',
        horizontalalignment='left',
    )

    ax = plt.gca()
    for edge in G.edges:
        ax.annotate(
            "",
            xy=pos[edge[1]], xycoords='data',
            xytext=pos[edge[0]], textcoords='data',
            arrowprops=dict(
                arrowstyle="->",
                color=color_of[edge[0]],
                shrinkA=5,
                shrinkB=5,
                patchA=None,
                patchB=None,
                connectionstyle=
                    "arc3,rad=0.0" if edge[1] == top_sort_next[edge[0]]
                    else "arc3,rad=-0.3",
                ),
        )

    ax.set_title(root)
    ax.axis("off")
    ax.set_xlim((-0.2, 0.8))
    ax.set_ylim((-1, len(order) - 1))

    plt.tight_layout()
    plt.show()


def draw_dot(plt, G, root):
    cmap = plt.get_cmap('viridis')
    colors = cmap(np.linspace(0, 1, len(G.nodes())))

    order = list(nx.topological_sort(G))
    index_of = {node: idx for idx, node in enumerate(order)}
    color_of = {node: colors[index_of[node]] for node in G.nodes()}
    colors = [colors[index_of[node]] for node in G.nodes()]
    edge_colors = [color_of[edge[0]] for edge in G.edges()]

    ax = plt.gca()
    ax.set_title(root)
    ax.axis("off")


    graphviz_args = '-Groot="{}"'.format(repr(root))
    pos = nx.drawing.nx_agraph.graphviz_layout(
        G, prog='dot', root=None, args=graphviz_args
    )
    pos = {node: (y, x) for node, (x, y) in pos.items()}
    nx.draw_networkx(
        G,
        pos=pos,
        node_size=50,
        node_color=colors,
        edge_color=edge_colors,
        with_labels=False
    )

    plt.show()


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


def identify_function(call, module):
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
    found = inspect.getmembers(
        module,
        lambda m: isinstance(m, xun.Function) and m.name == call.function_name
    )
    return found[0][1]


def interpret_call(call_string):
    """Interpret call

    Given a call string, return a call node representing the call. Expressions
    in the call are evaluated.

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
    if len(tree.body) != 1:
        raise SyntaxError('There must be exactly one statement in call string')

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
