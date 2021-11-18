"""Transformations

This module includes functionality for working with and manipulating function
code. The FunctionDecomposition class provides a data structure to make
managing code fragments easier, while the transformation functions are used to
generate xun scheduling and execution code.

The code is represented by and manipulated with the python ast module [1][2].

.. [1] Python ast documentation: https://docs.python.org/3/library/ast.html
.. [2] Greentreesnakes: https://greentreesnakes.readthedocs.io/en/latest/
"""


from .compatibility import ast
from .errors import XunInterfaceError
from .errors import XunSyntaxError
from .function_description import FunctionDescription
from .function_image import FunctionImage
from .util import assignment_target_introduced_names
from .util import assignment_target_shape
from .util import body_external_names
from .util import call_from_function_definition
from .util import function_ast
from .util import separate_constants_ast
from .util import shape_to_ast_tuple
from .util import sort_constants_ast
from itertools import chain
from typing import List
import copy
import functools


def assemble(desc, *nodes):
    """Assemble serializable `FunctionImage` representation

    Takes a list of lists of statements and assembles a serializable
    `FunctionImage` object.

    Parameters
    ----------
    *nodes : vararg of list of ast.AST nodes
        Lists of statements (in order) to be used as the statements of the
        generated function body

    Returns
    -------
    FunctionImage
        Serializable `FunctionImage` representation
    """
    args = desc.ast.body[0].args

    body = list(chain(*nodes))

    fdef = ast.fix_missing_locations(ast.Module(
        type_ignores=[],
        body=[
            ast.FunctionDef(
                name=desc.name,
                args=args,
                decorator_list=[],
                body=body,
                returns=None,
                type_comment=None,
            )
        ],
    ))

    f = FunctionImage(
        fdef,
        desc.name,
        desc.qualname,
        desc.doc,
        desc.annotations,
        desc.module,
        desc.globals,
        desc.referenced_modules,
    )

    return f


def pass_by_value(func):
    """
    NodeTransformers modify ASTs inplace, this decorator can be used to ensure
    such modifications don't leak back to the original description.
    """
    def wrapper(*args, **kwargs):
        return func(
            *[copy.deepcopy(a) for a in args],
            **{copy.deepcopy(k): copy.deepcopy(v) for k, v in kwargs.items()}
        )
    functools.update_wrapper(wrapper, func)
    return wrapper


#
# Transformations
#


@pass_by_value
def generate_header():
    """Generate header

    Provide a header with necessary statements.

    Returns
    -------
    List[ast.Ast]
    """
    return [
        ast.Assign(
            targets=[ast.Name(id='_xun_store', ctx=ast.Store())],
            value=ast.Yield(value=None),
            type_comment=None,
        ),
        ast.Expr(ast.Yield(value=None), type_ignores=[]),
    ]


@pass_by_value
def separate_constants(func_desc: FunctionDescription):
    """Separate constants

    Seperate the with constants from the body. The FunctionDecomposition is
    updated with new attributes `body` and `constants`. Attribute `ast` is
    deleted.

    Parameters
    ----------
    func_desc : FunctionDescription

    Returns
    -------
    FunctionDecomposition
    """
    body, constants = separate_constants_ast(func_desc.ast.body[0].body)
    return body, constants


@pass_by_value
def sort_constants(constants: List[ast.AST]):
    """Sort constants

    Sort the statements from the with constants statement such that they can be
    evaluated sequentially. The resulting FunctionDecomposition has new
    attributes `sorted_constants` and `constant_graph`. Attributes `constants`
    is deleted.

    Parameters
    ----------
    constants : List[ast.AST]

    Returns
    -------
    Tuple[List[ast.AST], List[ast.AST]]
    """
    sorted_constants, constant_graph = sort_constants_ast(constants)
    return sorted_constants, constant_graph


@pass_by_value
def copy_only_constants(sorted_constants: List[ast.AST], dependencies={}):
    """Copy only constants

    Working on the FunctionDecomposition `sorted_constants`. Change any
    expression leaving the with constants statement through function calls to a
    copy of the expression. Change any expression entering as a result of a
    function to a copy of that expression. This ensures that any value inside
    the with constants statement never changes, e.g. acts as if it is a value,
    never a reference. This is necessary to ensure immutability in constant
    fields, and is what is responsible for the constness of the fields. If a
    function took a reference to a value instead of a copy, it could change the
    value. This would result in us not being able to evaluate and know its value
    when scheduling, since order is arbitrary.

    Calls to xun functions will later be replaced by sentinel nodes, which are
    not copyable, and should therefore not be made copy only. Managing which
    statements to skip is done through the skip_if predicate.

    The `sorted_constants` attribute is replaced by `copy_only_constants`.

    Parameters
    ----------
    sorted_constants: List[ast.AST]
    dependencies : mapping from str to Function
        maps names of dependencies to their Functions

    Returns
    -------
    List[ast.AST]
    """
    def gen_deepcopy_expr(expr):
        deepcopy_id = ast.Name(id='_xun_deepcopy', ctx=ast.Load())
        return ast.Call(func=deepcopy_id, args=[expr], keywords=[])

    class CallArgumentCopyTransformer(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)

            if not isinstance(node.func, ast.Name):
                return node

            if node.func.id in dependencies:
                return node

            args = [gen_deepcopy_expr(arg) for arg in node.args]
            keywords = [
                ast.keyword(kw.arg, gen_deepcopy_expr(kw.value))
                for kw in node.keywords
            ]
            new_call = ast.Call(func=node.func, args=args, keywords=keywords)
            copy_result = gen_deepcopy_expr(new_call)
            return copy_result

    transformer = CallArgumentCopyTransformer()
    transformed = [transformer.visit(stmt) for stmt in sorted_constants]

    from_copy_import_deepcopy = ast.ImportFrom(
        module='copy',
        names=[ast.alias(name='deepcopy', asname='_xun_deepcopy')],
        level=0
    )
    copy_only_constants = [from_copy_import_deepcopy, *transformed]

    return copy_only_constants


@pass_by_value
def unpack_unpacking_assignments(copy_only_constants: List[ast.AST]):
    """Unpack Unpacking Assignments

    `CallNodes` cannot be unpacked directly. Therefore, we add a function
    `_xun_unpack` that enables structured unpacking of any indexable type,
    `CallNodes` included.

    Parameters
    ----------
    copy_only_constants : List[ast.AST]

    Returns
    -------
    List[ast.AST]

    Examples
    --------
    >>> a, b, (c, d) = _xun_CallNode('f')  # becomes
    >>> a, b, (c, d) = _xun_unpack((2, (2,)), _xun_CallNode('f'))

    >>> a, b, (c, d) = [1, 2, (3, 4)]  # becomes
    >>> a, b, (c, d) = _xun_unpack((2, (2, )), [1, 2, 3])
    """
    def lhs_is_iterable(node):
        return isinstance(node.targets[0], (ast.Tuple, ast.List))

    class UnpackUnpackingAssignments(ast.NodeTransformer):
        def visit_Assign(self, node):
            if not lhs_is_iterable(node):
                self.generic_visit(node)
                return node

            target_shape = assignment_target_shape(node.targets[0])

            # Transform starred assignments after finding the shape
            node = self.generic_visit(node)

            unpack_call = ast.Call(
                func=ast.Name(id='_xun_unpack', ctx=ast.Load()),
                args=[shape_to_ast_tuple(target_shape), node.value],
                keywords=[],
            )

            return ast.Assign(
                targets=node.targets,
                value=unpack_call,
                type_comment=None,
            )

        def visit_Starred(self, node):
            # Starred assignments work by slicing CallNodes
            if isinstance(node.ctx, ast.Load):
                return self.generic_visit(node)
            return self.generic_visit(node.value)

    transformer = UnpackUnpackingAssignments()
    transformed = [transformer.visit(stmt) for stmt in copy_only_constants]
    import_xun_unpack = ast.ImportFrom(
        module='xun.functions',
        names=[ast.alias(name='unpack', asname='_xun_unpack')],
        level=0
    )
    return [import_xun_unpack, *transformed]


@pass_by_value
def transform_yields(body: List[ast.AST], interfaces):
    """Transform Yields

    This transformation will change any yields from the form
    `yield xun_function(args) is value` to `yield xun_function(args), value`.

    Parameters
    ----------
    body : List[ast.AST]
    interfaces : mapping from interface name (str) to Interface

    Returns
    -------
    List[ast.AST]
    """
    class yield_transformer(ast.NodeTransformer):
        def visit_Expr(self, node):
            if not isinstance(node.value, ast.Yield):
                return node
            if not isinstance(node.value.value, ast.Compare):
                raise XunSyntaxError
            if not len(node.value.value.ops) == 1:
                raise XunSyntaxError
            if not isinstance(node.value.value.ops[0], ast.Is):
                raise XunSyntaxError
            call = node.value.value.left
            value = node.value.value.comparators[0]

            if call.func.id not in interfaces:
                msg = f'Missing interface definition for {call.func.id}'
                raise XunInterfaceError(msg)

            return ast.Expr(
                ast.Yield(ast.Tuple(
                    elts=[call, value],
                    ctx=ast.Load(),
                ))
            )
    y = yield_transformer()
    return [y.visit(stmt) for stmt in body]


@pass_by_value
def build_xun_graph(unpacked_assignments: List[ast.AST], dependencies={}):
    """Build Xun Graph Transformation

    This transformation will generate code such that any call to a xun function
    is registered in a graph. The new code will return a dependency graph for
    the function assembled from the FunctionDecomposition.

    This version of the code is final and will be run during scheduling.

    Parameters
    ----------
    unpacked_assignments : List[ast.AST]
    dependencies : mapping from str to Function
        maps names of dependencies to their Functions

    Returns
    -------
    List[ast.AST]
    """

    # The following code is never executed here, but is injected into the
    # FunctionDecomposition body. (`xun_graph` attribute). The injected code
    # provides a graph, and a funtion _xun_register_call that is used to
    # populate the graph.
    @function_ast
    def helper_code():
        from itertools import chain as _xun_chain
        from xun.functions import CallNode as _xun_CallNode
        import networkx as _xun_nx

        _xun_graph = _xun_nx.DiGraph()

        def _xun_register_call(fname,
                               fhash,
                               *args,
                               **kwargs):

            # Any references to results from other xun functions must be loaded
            dependencies = filter(
                lambda a: isinstance(a, _xun_CallNode),
                _xun_chain(args, kwargs.values())
            )
            call = _xun_CallNode(fname, fhash, *args, **kwargs)
            _xun_graph.add_node(call)
            _xun_graph.add_edges_from((dep, call) for dep in dependencies)
            return call

    header = helper_code.body[0].body

    class RegisterCallWrapper(ast.NodeTransformer):
        """
        Transformation any calls to a xun function to _xun_register_call
        """
        def visit_Call(self, node):
            node = self.generic_visit(node)

            if not isinstance(node.func, ast.Name):
                return node

            if node.func.id not in dependencies:
                return node

            register_call = ast.Call(
                func=ast.Name(id='_xun_register_call', ctx=ast.Load()),
                args=[
                    ast.Constant(node.func.id, kind=None),
                    ast.Constant(dependencies[node.func.id].hash, kind=None),
                    *node.args
                ],
                keywords=node.keywords,
                type_comment=None,
            )
            return register_call

    return_graph = ast.Return(value=ast.Name(id='_xun_graph', ctx=ast.Load()))

    body = [
        RegisterCallWrapper().visit(stmt)
        if isinstance(stmt, ast.Assign) or isinstance(stmt, ast.Expr)
        else stmt
        for stmt in unpacked_assignments
    ]

    xun_graph = [
        *header,
        *body,
        return_graph
    ]

    return xun_graph


@pass_by_value
def load_from_store(body: List[ast.AST],
                    unpacked_assignments: List[ast.AST],
                    dependencies={}):
    """Load from Store Transformation

    Transform any call to xun functions into loads from the xun store. This
    version of the function is final and will be run during execution.

    Parameters
    ----------
    body : List[ast.AST]
    unpacked_assignments : List[ast.AST]
    dependencies : mapping from str to Function
        maps names of dependencies to their Functions

    Returns
    -------
    List[ast.AST]
    """
    class DiscoverReferences(ast.NodeVisitor):
        def __init__(self):
            self.seen_targets = set()

            for node in unpacked_assignments:
                self.visit(node)

            self.body_external_names = body_external_names(body)

            self.referenced_in_body = sorted(
                self.seen_targets.intersection(self.body_external_names)
            )

        def visit_Assign(self, node):
            self.generic_visit(node)
            target = node.targets[0]
            self.seen_targets.update(
                assignment_target_introduced_names(target)
                if isinstance(target, (ast.Tuple, ast.List)) else [target.id]
            )
            return node
    discovered_reference = DiscoverReferences()

    def is_referenced_in_body(name):
        return name in discovered_reference.referenced_in_body

    def is_xun_call(node):
        return (
            isinstance(node, ast.Call) and
            isinstance(node.func, ast.Name) and
            node.func.id in dependencies
        )

    # If No dependencies are referenced in the body of the function, there is
    # nothing to load
    if len(discovered_reference.referenced_in_body) == 0:
        return []

    # Assigned values will be made available to the function body
    assignments = [
        node for node in unpacked_assignments if isinstance(node, ast.Assign)
    ]

    imports = [
        *[
            node for node in unpacked_assignments
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ],
    ]

    store_accessor_deepload = ast.Attribute(
        value=ast.Name(id='_xun_store', ctx=ast.Load()),
        attr='deepload',
        ctx=ast.Load(),
    )

    deep_load_referenced = ast.Call(
        func=store_accessor_deepload,
        args=[
            ast.Name(id=name, ctx=ast.Load())
            for name in discovered_reference.referenced_in_body
        ],
        keywords=[],
    )

    load_function = ast.FunctionDef(
        name='_xun_load_constants',
        args=ast.arguments(posonlyargs=[], args=[], vararg=None,
                           kwonlyargs=[], kw_defaults=[], kwarg=None,
                           defaults=[]),
        body=[
            *imports,
            *assignments,
            ast.Return(deep_load_referenced),
        ],
        decorator_list=[],
        returns=None,
        type_comment=None,
    )

    load_call = ast.Assign(
        targets=[
            ast.Tuple(
                elts=[
                    ast.Name(id=target, ctx=ast.Store())
                    for target in discovered_reference.referenced_in_body
                ],
                ctx=ast.Store(),
            )
        ],
        value=ast.Call(
            func=ast.Name(id='_xun_load_constants', ctx=ast.Load()),
            args=[],
            keywords=[],
        ),
        type_comment=None,
    )

    lfs = [
        load_function,
        load_call,
    ]

    return lfs


#
# Interface Transformations
#

@pass_by_value
def separate_interface_and_target(func_desc: FunctionDescription, target):
    fdef = func_desc.ast.body[0]
    interface_call = call_from_function_definition(fdef)

    if len(fdef.body) != 1 or not (
            isinstance(fdef.body[0], ast.Expr) and
            isinstance(fdef.body[0].value, ast.YieldFrom)):
        msg = 'Interface defintions should a single "yield from" expression'
        raise XunSyntaxError(msg)

    target_call = func_desc.ast.body[0].body[0].value.value

    if not isinstance(target_call, ast.Call):
        raise XunSyntaxError('Can only yield from calls to xun functions')

    if not target_call.func.id == target.name:
        msg = (
            f'Interface should yield from {target.name} not '
            f'{target_call.func.id}'
        )
        raise XunInterfaceError(msg)

    return interface_call, target_call


@pass_by_value
def build_interface_graph(interface_call: ast.expr, target_call: ast.expr):
    """Interface

    Transform function into an interface.

    Returns
    -------
    List[ast.Ast]
    """
    import_nx = ast.Import([ast.alias(name='networkx', asname='_xun_nx')])
    xun_graph = ast.Assign(
        targets=[ast.Name(id='_xun_graph', ctx=ast.Store())],
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='_xun_nx', ctx=ast.Load()),
                attr='DiGraph',
                ctx=ast.Load(),
            ),
            args=[],
            keywords=[],
        ),
        type_comment=None,
    )
    add_edge = ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id='_xun_graph', ctx=ast.Load()),
                attr='add_edge',
                ctx=ast.Load(),
            ),
            args=[target_call, interface_call],
            keywords=[],
        )
    )
    return_graph = ast.Return(ast.Name(id='_xun_graph', ctx=ast.Load()))

    return [
        import_nx,
        xun_graph,
        add_edge,
        return_graph,
    ]


@pass_by_value
def interface_raise_on_execution(interface_call: ast.expr,
                                 target_call: ast.expr):
    import_interface_error = ast.ImportFrom(
        module='xun.functions',
        names=[ast.alias(name='XunInterfaceError',
                         asname='_xun_InterfaceError')],
        level=0,
    )
    raise_interface_error = ast.Raise(
        exc=ast.Call(
            func=ast.Name(id='_xun_InterfaceError', ctx=ast.Load()),
            args=[
                ast.JoinedStr([
                    ast.FormattedValue(target_call, -1, None),
                    ast.Constant(
                        value=' did not produce a result for ',
                        kind=None,
                    ),
                    ast.FormattedValue(interface_call, -1, None),
                ]),
            ],
            keywords=[]
        ),
        cause=None,
    )
    return [
        import_interface_error,
        raise_interface_error,
    ]
