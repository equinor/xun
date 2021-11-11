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
from .util import separate_constants_ast
from .util import shape_to_ast_tuple
from .util import sort_constants_ast
from itertools import chain
from typing import List
import contextvars
import copy
import functools


def assemble(desc,
             *nodes,
             globals=None,
             hash=None,
             original_source_code=None,
             interface_hashes=frozenset()):
    """Assemble serializable `FunctionImage` representation

    Takes a list of lists of statements and assembles a serializable
    `FunctionImage` object.

    Parameters
    ----------
    desc : FunctionDescription
    *nodes : vararg of list of ast.AST nodes
        Lists of statements (in order) to be used as the statements of the
        generated function body
    globals : dict
        The assembled functions global scope
    hash : str
        Xun function hash
    original_source_code : str
        The source code of the original function this is generated from
    interface_hashes : frozenset[str]
        The hashes of any defined interface of the (xun?) function

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
        globals if globals is not None else desc.globals,
        desc.referenced_modules,
        original_source_code=original_source_code,
        interface_hashes=interface_hashes,
        hash=hash,
    )

    return f


def ast_pass_by_value(func):
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


@ast_pass_by_value
def generate_header():
    """Generate header

    Provide a header with necessary statements.

    Returns
    -------
    List[ast.Ast]
    """
    return [
        ast.Assign(
            targets=[ast.Name(id='_xun_store_accessor', ctx=ast.Store())],
            value=ast.Yield(value=None),
            type_comment=None,
        ),
        ast.Expr(ast.Yield(value=None), type_ignores=[]),
    ]


@ast_pass_by_value
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


@ast_pass_by_value
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


@ast_pass_by_value
def pass_by_value(sorted_constants: List[ast.AST]):
    """Pass by Value

    To ensure immutability calls to functions from xun defintions statements
    are done by value. That is any argument is copied before leaving the
    statement, and the return value is copied before it is exposed to the
    statement.

    Parameters
    ----------
    sorted_constants: List[ast.AST]

    Returns
    -------
    List[ast.AST]
    """
    class CallArgumentCopyTransformer(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)

            pass_by_value = ast.Name(id='_xun_pass_by_value', ctx=ast.Load())
            return ast.Call(func=pass_by_value,
                            args=[node.func, *node.args],
                            keywords=node.keywords)

    transformer = CallArgumentCopyTransformer()
    transformed = [transformer.visit(stmt) for stmt in sorted_constants]

    import_pass_by_value = ast.ImportFrom(
        module='xun.functions.runtime',
        names=[ast.alias(name='pass_by_value', asname='_xun_pass_by_value')],
        level=0
    )
    copy_only_constants = [import_pass_by_value, *transformed]

    return copy_only_constants


@ast_pass_by_value
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
        module='xun.functions.runtime',
        names=[ast.alias(name='unpack', asname='_xun_unpack')],
        level=0
    )
    return [import_xun_unpack, *transformed]


@ast_pass_by_value
def build_xun_graph(unpacked_assignments: List[ast.AST]):
    """Build Xun Graph Transformation

    This transformation will generate code such that any call to a xun function
    is registered in a graph. The new code will return a dependency graph for
    the function assembled from the FunctionDecomposition.

    This version of the code is final and will be run during scheduling.

    Parameters
    ----------
    unpacked_assignments : List[ast.AST]

    Returns
    -------
    List[ast.AST]
    """
    class AssignVisitor(ast.NodeVisitor):
        def __init__(self):
            self.introduced_names = set()

            for node in unpacked_assignments:
                self.visit(node)

        def visit_Assign(self, node):
            self.generic_visit(node)
            target = node.targets[0]
            self.introduced_names.update(
                assignment_target_introduced_names(target)
            )

    assign_visitor = AssignVisitor()

    import_detect_dependencies_by_deepcopy = ast.ImportFrom(
        module='xun.functions.runtime',
        names=[
            ast.alias(
                name='detect_dependencies_by_deepcopy',
                asname='_xun_detect_dependencies_by_deepcopy',
            ),
        ],
        level=0
    )

    detect_dependencies_by_deepcopy = ast.Name(
        id='_xun_detect_dependencies_by_deepcopy', context=ast.Load())

    unnamed_statements = [
        expr for expr in unpacked_assignments
        if isinstance(expr, ast.Expr)
    ]

    named_statements = [
        stmt for stmt in unpacked_assignments
        if not isinstance(stmt, ast.Expr)
    ]

    call_detect_dependencies_by_deepcopy = ast.Call(
        func=detect_dependencies_by_deepcopy,
        args=[
            *[
                ast.Name(id=name, ctx=ast.Load())
                for name in assign_visitor.introduced_names
            ],
            *[expr for expr in unnamed_statements],
        ],
        keywords=[],
    )

    return [
        import_detect_dependencies_by_deepcopy,
        *named_statements,
        ast.Return(call_detect_dependencies_by_deepcopy),
    ]


@ast_pass_by_value
def load_args(body: List[ast.AST], function_arg_names):
    import_load_args = ast.ImportFrom(
        module='xun.functions.runtime',
        names=[ast.alias(name='resolve_args_by_deepcopy',
                         asname='_xun_resolve_args_by_deepcopy')],
        level=0,
    )
    load_args = ast.Assign(
        targets=[
            ast.Tuple(
                elts=[
                    *[
                        ast.Name(id=name, ctx=ast.Store())
                        for name in function_arg_names
                    ],
                    ast.Name(id='_xun_symbolic_args', ctx=ast.Store()),
                ],
                ctx=ast.Store(),
            )
        ],
        value=ast.Call(
            func=ast.Name(id='_xun_resolve_args_by_deepcopy', ctx=ast.Load()),
            args=[
                ast.Name(
                    id='_xun_store_accessor',
                    ctx=ast.Load()
                ),
            ],
            keywords=[
                ast.keyword(arg=name, value=ast.Name(id=name, ctx=ast.Load()))
                for name in function_arg_names
            ],
        ),
        type_comment=None,
    )
    return [
        import_load_args,
        load_args,
        *body,
    ]


@ast_pass_by_value
def transform_yields(body: List[ast.AST], function_arg_names):
    """Transform Yields

    This transformation will change any yields from the form
    `yield xun_function(args) is value` to `yield xun_function(args), value`.

    Parameters
    ----------
    body : List[ast.AST]
    function_arg_names : List[str]

    Returns
    -------
    List[ast.AST]
    """
    class yield_transformer(ast.NodeTransformer):
        is_interface_args = contextvars.ContextVar(
            'is_interface_args', default=False)

        def visit_Expr(self, node):
            if not isinstance(node.value, ast.Yield):
                return node
            if not isinstance(node.value.value, ast.Compare):
                raise XunSyntaxError
            if not len(node.value.value.ops) == 1:
                raise XunSyntaxError
            if not isinstance(node.value.value.ops[0], ast.Is):
                raise XunSyntaxError

            original_call = node.value.value.left

            argctx = contextvars.copy_context()
            argctx.run(yield_transformer.is_interface_args.set, True)
            call = argctx.run(self.generic_visit, original_call)

            value = node.value.value.comparators[0]

            # if call.func.id not in interfaces:
            #     msg = f'Missing interface definition for {call.func.id}'
            #     raise XunInterfaceError(msg)

            return ast.Expr(
                ast.Yield(ast.Tuple(
                    elts=[call, value],
                    ctx=ast.Load(),
                ))
            )

        def visit_Name(self, node):
            is_interface_args = yield_transformer.is_interface_args.get()
            if is_interface_args and node.id in function_arg_names:
                return ast.Attribute(
                    value=ast.Name(id='_xun_symbolic_args', ctx=ast.Load()),
                    attr=node.id,
                    ctx=ast.Load(),
                )
            return node

    y = yield_transformer()
    return [y.visit(stmt) for stmt in body]


@ast_pass_by_value
def load_constants(body: List[ast.AST], unpacked_assignments: List[ast.AST]):
    """Load from Store Transformation

    Transform any call to xun functions into loads from the xun store. This
    version of the function is final and will be run during execution.

    Parameters
    ----------
    body : List[ast.AST]
    unpacked_assignments : List[ast.AST]

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

    # If No dependencies are referenced in the body of the function, there is
    # nothing to load
    if len(discovered_reference.referenced_in_body) == 0:
        return []

    # Assigned values will be made available to the function body
    assignments = [
        node for node in unpacked_assignments if isinstance(node, ast.Assign)
    ]

    imports = [
        ast.ImportFrom(
            module='xun.functions.runtime',
            names=[ast.alias(name='load_results_by_deepcopy',
                             asname='_xun_load_results_by_deepcopy')],
            level=0,
        ),
        *[
            node for node in unpacked_assignments
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ],
    ]

    deep_load_referenced = ast.Call(
        func=ast.Name(
            id='_xun_load_results_by_deepcopy',
            ctx=ast.Load()
        ),
        args=[
            ast.Name(
                id='_xun_store_accessor',
                ctx=ast.Load()
            ),
            *[
                ast.Name(id=name, ctx=ast.Load())
                for name in discovered_reference.referenced_in_body
            ],
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

@ast_pass_by_value
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


@ast_pass_by_value
def build_interface_graph(interface_call: ast.expr, target_call: ast.expr):
    """Interface

    Transform function into an interface.

    Returns
    -------
    List[ast.Ast]
    """
    import_detect_dependencies_by_deepcopy = ast.ImportFrom(
        module='xun.functions.runtime',
        names=[
            ast.alias(
                name='detect_dependencies_by_deepcopy',
                asname='_xun_detect_dependencies_by_deepcopy',
            ),
        ],
        level=0
    )
    detect_dependencies_by_deepcopy = ast.Name(
        id='_xun_detect_dependencies_by_deepcopy', ctx=ast.Load())

    xun_graph = ast.Assign(
        targets=[ast.Name(id='_xun_graph', ctx=ast.Store())],
        value=ast.Call(
            func=detect_dependencies_by_deepcopy,
            args=[target_call],
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
        import_detect_dependencies_by_deepcopy,
        xun_graph,
        add_edge,
        return_graph,
    ]


@ast_pass_by_value
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
