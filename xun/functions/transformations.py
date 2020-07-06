from .functions import Function
from .functions import NotDAGError
from .functions import function_ast
from collections import Counter
from itertools import chain
from itertools import tee
import ast
import networkx as nx


#
# Transformations
#

def separate_constants(func: Function):
    ast_it0, ast_it1 = tee(func.ast)
    body = [stmt for stmt in ast_it0 if not is_with_constants(stmt)]
    with_constants = [stmt for stmt in ast_it1 if is_with_constants(stmt)]

    if len(with_constants) > 1:
        msg = 'Functions must have at most one with constants statement'
        raise ValueError(msg)

    constants = []
    if len(with_constants) == 1:
        check_with_constants(with_constants[0])
        constants = with_constants[0].body

    return func.update(['ast'], {'body': body, 'constants': constants})


def sort_constants(func: Function):
    constant_graph = stmt_dag(func.constants)
    sorted_constants = [ node for node in nx.topological_sort(constant_graph)
                         if isinstance(node, ast.AST) ]

    return func.update(
        ['constants'],
        {
            'sorted_constants': sorted_constants,
            'constant_graph': constant_graph,
        }
    )


def copy_only_constants(func: Function, ignore_predicate=lambda _: False):
    def make_expr_deepcopy(expr):
        deepcopy_id = ast.Name(id='deepcopy', ctx=ast.Load())
        return ast.Call(deepcopy_id, args=[expr], keywords=[])

    class CallArgumentCopyTransformer(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)

            if ignore_predicate(node):
                return node

            args = [make_expr_deepcopy(arg) for arg in node.args]
            keywords = [
                ast.keyword(kw.arg, make_expr_deepcopy(kw.value))
                for kw in node.keywords
            ]
            new_call = ast.Call(func=node.func, args=args, keywords=keywords)
            copy_result = make_expr_deepcopy(new_call)
            return copy_result

    transformer = CallArgumentCopyTransformer()
    transformed = [transformer.visit(stmt) for stmt in func.sorted_constants]

    from_copy_import_deepcopy = ast.ImportFrom(
        module='copy',
        names=[ast.alias(name='deepcopy')],
    )
    copy_only_constants = [from_copy_import_deepcopy, *transformed]

    return func.update(
        ['sorted_constants'],
        {
            'copy_only_constants': copy_only_constants,
        },
    )


def build_xun_graph(func: Function, context):
    @function_ast
    def helper_code():
        from xun.functions import CallNode as _xun_CallNode
        from xun.functions import CopyError as _xun_CopyError
        from xun.functions import TargetNameNode as _xun_TargetNameNode
        from xun.functions import SentinelNode as _xun_SentinelNode
        import networkx as _xun_nx

        _xun_graph = _xun_nx.DiGraph()

        def _xun_register_sentinel(fname,
                                   external_names,
                                   targets,
                                   *args,
                                   **kwargs):
            dependencies = list(
                filter(
                    lambda a: a in _xun_graph,
                    map(_xun_TargetNameNode, external_names)
                )
            )
            outputs = [_xun_TargetNameNode(name) for name in targets]
            call = _xun_CallNode(fname, *args, **kwargs)
            _xun_graph.add_node(call)
            _xun_graph.add_edges_from((dep, call) for dep in dependencies)
            _xun_graph.add_edges_from((call, tar) for tar in outputs)
            return _xun_SentinelNode(call)
    header = helper_code.body[0].body

    def str_list_to_ast(L):
        literal = ast.List(
            elts=[ast.Constant(el) for el in L],
            ctx=ast.Load(),
        )
        return literal

    class XCall(ast.NodeTransformer):
        def __init__(self, stmt):
            self.targets = stmt_targets(stmt)
            self.external_xun_names = stmt_external_names(stmt)

        def visit_Call(self, node):
            node = self.generic_visit(node)

            if not isinstance(node.func, ast.Name):
                return node

            if node.func.id not in context:
                return node

            new_node = ast.Call(
                func=ast.Name(id='_xun_register_sentinel', ctx=ast.Load()),
                args=[
                    ast.Constant(node.func.id),
                    str_list_to_ast(self.external_xun_names),
                    str_list_to_ast(self.targets),
                    *node.args
                ],
                keywords=node.keywords,
            )
            return new_node

    return_graph = ast.Return(value=ast.Name(id='_xun_graph', ctx=ast.Load()))

    xun_graph = [
        *header,
        *(
            XCall(stmt).visit(stmt)
            if isinstance(stmt, ast.Assign)
            or isinstance(stmt, ast.Expr)
            else stmt
            for stmt in func.copy_only_constants
        ),
        return_graph
    ]

    return func.update(
        ['copy_only_constants'],
        {
            'xun_graph': xun_graph,
        },
    )


def load_from_store(func: Function, context):
    class LoadTransformer(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)

            if not isinstance(node.func, ast.Name):
                return node

            if node.func.id not in context:
                return node

            construct_call = ast.Call(
                func=ast.Name(id='_xun_CallNode', ctx=ast.Load()),
                args=[
                    ast.Constant(node.func.id),
                    *node.args,
                ],
                keywords=[]
            )

            new_node = ast.Subscript(
                value=ast.Name(id='_xun_store', ctx=ast.Load()),
                slice=ast.Index(value=construct_call),
                ctx=ast.Load(),
            )
            return new_node

    from_xun_functions_import_call = ast.ImportFrom(
        module='xun.functions',
        names=[ast.alias(name='CallNode', asname='_xun_CallNode')],
    )

    lfs = [
        from_xun_functions_import_call,
        *(
            LoadTransformer().visit(stmt) for stmt in func.copy_only_constants
        ),
    ]

    return func.update(
        ['copy_only_constants'],
        {
            'load_from_store': lfs,
        },
    )

#
# Predicates and checks
#

def check_with_constants(node):
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
    return all(
        isinstance(node, ast.Assign)
        or isinstance(node, ast.Expression)
        for node in node.body
    )


def no_reassignments(node):
    names = chain(*[
        target_names(assign.targets)
        for assign in node.body
        if isinstance(assign, ast.Assign)
    ])
    return all(count == 1 for count in Counter(names).values())


#
# Helpers
#

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
