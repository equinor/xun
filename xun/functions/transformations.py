from .function_image import FunctionImage
from .functions import function_ast
from .functions import separate_constants_ast
from .functions import sort_constants_ast
from .functions import stmt_external_names
from .functions import stmt_targets
import ast


#
# Transformations
#

def separate_constants(func: FunctionImage):
    """Separate constants

    Seperate the with constants from the body. The FunctionImage is updated with
    new attributes `body` and `constants`. Attribute `ast` is deleted.

    Parameters
    ----------
    func : FunctionImage

    Returns
    -------
    FunctionImage
    """
    body, constants = separate_constants_ast(func.ast.body[0].body)
    return func.update(['ast'], {'body': body, 'constants': constants})


def sort_constants(func: FunctionImage):
    """Sort constants

    Sort the statements from the with constants statement such that they can be
    evaluated sequentially. The resulting FunctionImage has new attributes
    `sorted_constants` and `constant_graph`. Attributes `constants` is deleted.

    Parameters
    ----------
    func : FunctionImage

    Returns
    -------
    FunctionImage
    """
    sorted_constants, constant_graph = sort_constants_ast(func.constants)
    return func.update(
        ['constants'],
        {
            'sorted_constants': sorted_constants,
            'constant_graph': constant_graph,
        }
    )


def copy_only_constants(func: FunctionImage, ignore_predicate=lambda _: False):
    """Copy only constants

    Working on the FunctionImage `sorted_constants`. Change any expression
    leaving the with constants statement through function calls to a copy of the
    expression. Change any expression entering as a result of a function to a
    copy of that expression. This ensures that any value inside the with
    constants statement neven changes.

    Calls to context functions will later be replaced by sentinel nodes, which
    are not copyable, and should therefore not be made copy only. Managing which
    statments to skip is done through the ignore_predicate predicate.

    The `sorted_constants` attribute is replaced by `copy_only_constants`.

    Parameters
    ----------
    func : FunctionImage
    ignore_predicate : callable, optional
        This predicate is made available because we do not was to alter any
        calls to context functions as these should not be copy only.

    Returns
    -------
    FunctionImage
    """
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


def build_xun_graph(func: FunctionImage, context):
    """Build Xun Graph Transformation

    This transformation will generated code from a FunctionImage's
    copy_only_constants such that any call to a context function is replaced by
    an uncopyable SentinelNode and registered in a graph. The new code will
    return a dependency graph for the function assembled from the FunctionImage.

    This version of the code is final and will be run during scheduling.

    Attribute `copy_only_constants` is replaced by `xun_graph`.

    Parameters
    ----------
    func : FunctionImage
    context : xun.context
        the context that the call/dependency graph will be built from

    Returns
    -------
    FunctionImage
    """

    # The following code is never executed here, but is injected into the
    # FunctionImage body. (`xun_graph` attribute)
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


def load_from_store(func: FunctionImage, context):
    """Load from Store Transformation

    Transform any call to context functions into loads from the context store.
    This version of the function is final and will be run during execution.

    Attribute `copy_only_constants` is replaced by `load_from_store`.

    Parameters
    ----------
    func : FunctionImage
    context : xun.context
        the context that owns this function and the store

    Returns
    -------
    FunctionImage
    """
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
