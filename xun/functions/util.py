from .errors import NotDAGError
from collections import Counter
from itertools import chain
from itertools import tee
import ast
import copy
import inspect
import networkx as nx
import textwrap
import types


#
# Functions
#


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


#
# AST helpers
#


def function_source(func):
    """Function Source

    Get the source code of a function. Cannot be done on dynamically generated
    functions.

    Returns
    -------
    str
        Function source code
    """
    source = inspect.getsource(func)
    dedent = textwrap.dedent(source)
    return dedent


def function_ast(func):
    """Function AST

    Get an abstract syntax tree of a function

    Returns
    -------
    ast.Module
        Abstract syntax tree of the function
    """
    src = function_source(func)
    return ast.parse(src)


def strip_decorators(tree):
    """Strip decorators

    Strip any decorators from a function ast

    Parameters
    ----------
    tree : ast.Module
        Function AST

    Returns
    -------
    ast.Module
        Function AST without decorators
    """
    fdef = tree.body[0]
    new = ast.Module(
        type_ignores=tree.type_ignores,
        body=[
            ast.FunctionDef(
                name=fdef.name,
                args=fdef.args,
                body=fdef.body,
                decorator_list=[],
                returns=fdef.returns,
                type_comment=fdef.type_comment,
            )
        ]
    )
    return ast.fix_missing_locations(new)


def separate_constants_ast(stmts: [ast.AST]):
    """Separate constants from ast statements

    Given a list of statements, separate them into statements directly defined
    in the function body, and statements defined in a 'with constants'
    statement.

    Parameters
    ----------
    stmts : list of ast.AST
        statements to separate

    Returns
    -------
    tuple of lists of statements
        (body, constants)
    """
    ast_it0, ast_it1 = tee(stmts)
    body = [stmt for stmt in ast_it0 if not is_with_constants(stmt)]
    with_constants = [stmt for stmt in ast_it1 if is_with_constants(stmt)]

    if len(with_constants) > 1:
        msg = 'Functions must have at most one with constants statement'
        raise ValueError(msg)

    constants = []
    if len(with_constants) == 1:
        check_with_constants(with_constants[0])
        constants = with_constants[0].body

    return body, constants


def sort_constants_ast(stmts: [ast.AST]):
    """Sort with constants statements

    The with constants statement grammar lets you write statements in arbitrary
    order. To make this runnable python code, a sorting that allows sequential
    execution need to be found. This is done by constructina a statement
    dependency graph, which is required to be a directed acyclic graph, and
    computing a topological sort.

    Parameters
    ----------
    stmts : list of statements
        The statements to be sorted

    Returns
    -------
    list of ast.AST, nx.DiGraph
        The sorted statements and the statement dependency graph

    """
    constant_graph = stmt_dag(stmts)
    sorted_constants = [
        node for node in nx.topological_sort(constant_graph)
        if isinstance(node, ast.AST)
    ]
    return sorted_constants, constant_graph


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
        return frozenset(chain(*[target_names(u) for u in t]))
    elif isinstance(t, tuple):
        return frozenset(chain(*[target_names(u) for u in t]))
    elif isinstance(t, ast.Starred):
        return target_names(t.value)
    elif isinstance(t, ast.Name):
        return frozenset({t.id})
    else:
        raise TypeError('{}'.format(t))


def stmt_targets(stmt):
    """
    Return a list of all target names for a statement
    """
    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
        return frozenset(
            n.asname if n.asname is not None
            else n.name
            for n in stmt.names
        )
    try:
        targets = stmt.targets
        return target_names(targets)
    except AttributeError:
        return frozenset()


def stmt_external_names(stmt):
    """
    Return a list of names of all external names referenced by the statement
    """
    assign_types = (ast.Assign, ast.AugAssign, ast.AnnAssign)
    comp_types = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    import_types = (ast.Import, ast.ImportFrom)

    def comp_targets(node):
        targets = frozenset()
        for gen in node.generators:
            targets |= target_names(gen.target)
        return targets

    def visit_children(node, locals):
        return frozenset(
            chain(
                *(
                    external_names(c, locals)
                    for c in ast.iter_child_nodes(node)
                )
            )
        )

    def external_names(e, locals=frozenset()):
        if isinstance(e, ast.Name):
            if e.id not in locals:
                return frozenset({e.id})
            else:
                return frozenset()

        elif isinstance(e, ast.NamedExpr):
            raise NotImplementedError('Named expressions are not supported')

        elif isinstance(e, assign_types):
            if isinstance(e, ast.AnnAssign):
                msg = 'Annotated assignment not implemented'
                raise NotImplementedError(msg)
            return visit_children(e.value, locals)

        elif isinstance(e, comp_types):
            new_locals = locals | comp_targets(e)
            return visit_children(e, new_locals)

        elif isinstance(e, ast.For):
            new_locals = locals | target_names(e.target)
            return ( external_names(e.iter, locals) # Independed of new scope
                   | body_external_names(e.body, new_locals)
                   | body_external_names(e.orelse, new_locals)
                   )

        elif isinstance(e, import_types):
            return frozenset()

        else:
            return visit_children(e, locals)

    return external_names(stmt)


def fdef_decorator_external_names(fdef):
    """FunctionDef external names

    Function definitions may depend on external names from their decorators.
    Returns any referenced external names

    Parameters
    ----------
    fdef : ast.FunctionDef
        The function definition AST

    Returns
    -------
    frozenset of str
        Referenced external names
    """
    found = frozenset()
    for expr in fdef.decorator_list:
        found |= stmt_external_names(expr)
    return found


def body_external_names(stmts, locals=frozenset()):
    """Body external names

    Given a list of statements, returns any referenced name not created by
    previous statements, or in locals

    Parameters
    ----------
    stmts : list of statements
        body
    locals : frozenset of str
        Any locally defined names, usually used in recursive calls

    Returns
    -------
    frozenset of str
        The externally referenced names
    """
    local = set(locals)
    names = set()

    for stmt in stmts:
        targets = stmt_targets(stmt)
        external_names = stmt_external_names(stmt)
        names.update(name for name in external_names if name not in local)
        local.update(targets)

    return frozenset(names)


def func_external_names(fdef):
    """Function external names

    given a function definition ast, return all externally referenced names.

    Parameters
    ----------
    fdef : ast.FunctionDef
        The function definition AST

    Returns
    -------
    frozenset of str
        The externally referenced names
    """
    locals = argnames(fdef)
    body, constants = separate_constants_ast(fdef.body)
    sorted_constants, _ = sort_constants_ast(constants)
    stmts = list(chain(sorted_constants, body))
    return ( fdef_decorator_external_names(fdef)
           | body_external_names(stmts, locals=locals)
           )


def argnames(fdef):
    """FunctionDef argument names

    Given a function definition ast, return the names of all it's arguments

    Parameters
    ----------
    fdef : ast.FunctionDef
        The function definition AST

    Returns
    -------
    frozenset of str
        argument names
    """
    args = frozenset()
    args |= frozenset(a.arg for a in fdef.args.posonlyargs)
    args |= frozenset(a.arg for a in fdef.args.args)
    args |= frozenset(a.arg for a in fdef.args.kwonlyargs)
    if fdef.args.vararg is not None:
        args |= {fdef.args.vararg.arg}
    if fdef.args.kwarg is not None:
        args |= {fdef.args.kwarg.arg}
    return args



#
# AST Predicates and Checks
#


def check_with_constants(node):
    """Check with constants

    Raises
    ------
    ValueError
        If the node is not a valid with constants statement
    """
    if not is_with_constants(node):
        msg = 'Not an with constants statement: {}'
        raise ValueError(msg.format(node))
    if not is_assignments_and_expressions(node):
        msg = ('With constants statement can only contain assignments and '
               'expressions: {}')
        raise ValueError(msg.format(node))
    if not no_reassignments(node):
        msg = 'Reassigments not allowed in with constants statement: {}'
        raise ValueError(msg.format(node))


def is_with_constants(node):
    """Is with constants statement

    Returns
    -------
    bool
        Whether or not the node is a with constants statement
    """
    if not isinstance(node, ast.With):
        return False
    try:
        items = node.items

        if len(items) != 1:
            return False

        context_expr = items[0].context_expr

        return isinstance(context_expr, ast.Ellipsis)
    except AttributeError:
        return False
    except IndexError:
        return False


def is_assignments_and_expressions(node):
    """Is assignments and expressions

    Returns
    -------
    bool
        Whether or not the node's body contains exclusively assignment and
        expression statements
    """
    return all(
        isinstance(node, ast.Assign)
        or isinstance(node, ast.Expression)
        for node in node.body
    )


def no_reassignments(node):
    """No re-assignments

    Returns
    -------
    bool
        Whether or not the node never re-assigns a name
    """
    names = chain(*[
        target_names(assign.targets)
        for assign in node.body
        if isinstance(assign, ast.Assign)
    ])
    return all(count == 1 for count in Counter(names).values())
