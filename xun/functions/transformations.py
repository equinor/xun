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
    body, constants = separate_constants_ast(func.ast.body[0].body)
    return func.update(['ast'], {'body': body, 'constants': constants})


def sort_constants(func: FunctionImage):
    sorted_constants, constant_graph = sort_constants_ast(func.constants)
    return func.update(
        ['constants'],
        {
            'sorted_constants': sorted_constants,
            'constant_graph': constant_graph,
        }
    )


def copy_only_constants(func: FunctionImage, ignore_predicate=lambda _: False):
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