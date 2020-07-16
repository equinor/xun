from collections import namedtuple
from itertools import chain
import ast
import copy
import inspect
import networkx as nx
import textwrap
import types


class ContextError(Exception): pass
class CopyError(Exception): pass
class FunctionDefNotFoundError(Exception): pass
class FunctionError(Exception): pass
class NotDAGError(Exception): pass


def overwrite_globals(func, globals, defaults=None, module=None):
    """
    Returns a new function, with the same code as the given, but with the given
    scope
    """
    g = types.FunctionType(
        func.__code__,
        globals,
        name=func.__name__,
        argdefs=defaults if defaults is not None else func.__defaults__,
        closure=func.__closure__,
    )
    if module is not None:
        g.__module__ = module
    g.__kwdefaults__ = copy.copy(func.__kwdefaults__)
    return g


def describe(func):
    print('describing {}, from module {}'.format(func.__name__, func.__module__))
    tree = function_ast(func)

    is_single_function_module = (
        isinstance(tree, ast.Module)
        and len(tree.body) == 1
        and isinstance(tree.body[0], ast.FunctionDef)
    )

    if not is_single_function_module:
        raise ValueError('can only describe a single function')

    func_tree = tree.body[0]

    describer = Describer()
    describer.visit(func_tree)

    return FunctionInfo(
        ast=func_tree,
        name=describer.func_name,
        defaults=func.__defaults__,
        globals={},
        module=func.__module__,
    )


FunctionInfo = namedtuple(
    'FunctionInfo',
    [
        'ast',
        'name',
        'defaults',
        'globals',
        'module',
    ]
)


class Describer(ast.NodeVisitor):
    def __init__(self):
        self.func_node = None
        self.func_name = None

    def visit(self, node):
        r = super().visit(node)

        if self.func_node is None:
            raise FunctionDefNotFoundError('Could not find function definition')

        return r

    def visit_FunctionDef(self, node):
        if self.func_node is not None:
            raise FunctionError('More than one function definition')
        self.func_node = node
        self.func_name = node.name


#
# AST helpers
#


def function_ast(func):
    source = inspect.getsource(func)
    dedent = textwrap.dedent(source)
    return ast.parse(dedent)


def stmt_dag(stmts):
    """
    Create directed acyclic graph from a list of statements
    """
    G = nx.DiGraph()
    for stmt in stmts:
        inputs = stmt_external_names(stmt)
        outputs = stmt_targets(stmt)
        G.add_node(stmt)
        G.add_edges_from((i, stmt) for i in inputs)
        G.add_edges_from((stmt, o) for o in outputs)
    if not nx.is_directed_acyclic_graph(G):
        raise NotDAGError('Graph is not directed acyclic graph')
    return G


def target_names(t):
    """
    given a target expression node, return the names of all targets
    """
    if isinstance(t, list):
        return list(chain(*[target_names(u) for u in t]))
    elif isinstance(t, tuple):
        return list(chain(*[target_names(u) for u in t]))
    elif isinstance(t, ast.Starred):
        return target_names(t.value)
    elif isinstance(t, ast.Name):
        return [t.id]
    else:
        raise TypeError('{}'.format(t))



def stmt_targets(stmt):
    """
    Return a list of all target names for a statement
    """
    return target_names(stmt.targets)


def stmt_external_names(stmt):
    """
    Return a list of names of all external names referenced by the statement
    """
    comp_types = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)

    def comp_targets(node):
        targets = []
        for gen in node.generators:
            targets.extend(target_names(gen.target))
        return targets

    def visit_children(node, scope):
        return list(chain(
            *[external_names(c, scope) for c in ast.iter_child_nodes(node)]
        ))

    def external_names(e, scope=frozenset()):
        if isinstance(e, ast.Name):
            return [e.id] if e.id not in scope else []
        elif isinstance(e, comp_types):
            new_scope = scope | frozenset(comp_targets(e))
            return visit_children(e, new_scope)
        else:
            return visit_children(e, scope)

    return external_names(stmt.value)


def stmt_target_referenced(stmt):
    return stmt_targets(stmt), stmt_external_names(stmt)
