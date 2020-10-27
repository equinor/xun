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
from .function_description import FunctionDescription
from .function_description import describe
from .function_image import FunctionImage
from .util import assignment_target_names
from .util import assignment_target_shape
from .util import shape_to_ast_tuple
from .util import body_external_names
from .util import function_ast
from .util import separate_constants_ast
from .util import sort_constants_ast
from .util import stmt_external_names
from .util import stmt_introduced_names
from itertools import chain
import copy
import types


class FunctionDecomposition(types.SimpleNamespace):
    """ FunctionDecomposition

    Immutable decomposition of a function. Instance of FunctionDecomposition are
    used to transform functions as represented by syntax trees.

    Methods
    -------
    apply(transform, *args, **kwargs)
        Apply transform and return new FunctionDecomposition
    assemble(*nodes)
        Assemble FunctionDecomposition into Function object with the given
        function body ast.AST nodes.
    update(changed, new_desc)
        Create a new FunctionDecomposition object with the given changes

    Examples
    --------

    Apply transformations to a FunctionDecomposition

    >>> def func():
    ...     return 1
    ...     return 2
    ...
    >>> def transformation(img: FunctionDecomposition):
    ...     # remove first return
    ...     cropped_ast = img.ast.body[0].body[:1]
    ...     return img.update(
    ...         # Delete the original ast from FunctionDecomposition
    ...         ['ast'],
    ...         {
    ...             # Add cropped_ast as attribute
    ...             'cropped_ast': cropped_ast,
    ...         }
    ...     )
    ...
    >>> img = FunctionDecomposition(func)
    >>> transformed = img.apply(transformation)
    >>> f = img.assemble(img.ast.body[0].body)
    >>> g = transformed.assemble(transformed.cropped_ast)
    >>> f()
    1
    >>> g()
    2
    """
    def __init__(self, func_or_desc, attrs=None):
        self.desc = (
            func_or_desc if isinstance(func_or_desc, FunctionDescription)
            else describe(func_or_desc)
        )
        self.ast = copy.deepcopy(self.desc.ast)

        if attrs is not None:
            self.__dict__.update(attrs)

        self._lock = True

    @property
    def attrs(self):
        skipped = ('desc', 'ast', '_lock')
        return {k: v for k, v in self.__dict__.items() if k not in skipped}

    def __copy__(self):
        # Some of the attribute magic breaks copy
        return FunctionDecomposition(self.desc, self.attrs)

    def __setattr__(self, name, value):
        if hasattr(self, '_lock'):
            raise AttributeError('can\'t set attribute')
        super().__setattr__(name, value)

    def apply(self, transformation, *args, **kwargs):
        """Apply transformation

        Parameters
        ----------
        transformation : callable
            Callable that takes a FunctionDecomposition, computes new attributes
            and returns a new, updated FunctionDecomposition. This is typically
            a function of the following form::

                def transform(image: FunctionDecomposition) -> FunctionDecomposition:
                    ...
                    return image.update(
                        new_attributes,
                    )
        *args
            Arguments to pass to the transformation function
        **kwargs
            Keyword arguments to pass to the transformation function

        Returns
        -------
        FunctionDecomposition
            The transformed function image
        """
        return transformation(copy.copy(self), *args, **kwargs)

    def assemble(self, *nodes):
        """Assemble serializable `FunctionImage` representation

        Takes a list of lists of statements and assembles a serializable
        `FunctionImage` object.

        Parameters
        ----------
        *nodes : vararg of list of ast.AST nodes
            lists of statements (in order) to be used as the statements of the
            generated function body

        Returns
        -------
        FunctionImage
            Serializable `FunctionImage` representation
        """
        args = self.desc.ast.body[0].args

        body = list(chain(*nodes))

        fdef = ast.fix_missing_locations(ast.Module(
            type_ignores=[],
            body=[
                ast.FunctionDef(
                    name=self.desc.name,
                    args=args,
                    decorator_list=[],
                    body=body,
                )
            ],
        ))

        f = FunctionImage(
            fdef,
            self.desc.name,
            self.desc.globals,
            self.desc.referenced_modules,
        )

        return f

    def update(self, **kwargs):
        """Update

        Create a new FunctionDecomposition object with the given changes

        Parameters
        ----------
        changed : Mapping from str to Any
            Dictionary containing the new fields to be added to the
            FunctionDecomposition
        new_desc : xun.functions.FunctionDescription, optional
            use with care, replaces the underlying function description

        Returns
        -------
        FunctionDecomposition
            The updated FunctionDecomposition
        """
        attrs = self.attrs
        attrs.update(kwargs)
        return FunctionDecomposition(self.desc, attrs)


#
# Transformations
#

def separate_constants(func: FunctionDecomposition):
    """Separate constants

    Seperate the with constants from the body. The FunctionDecomposition is
    updated with new attributes `body` and `constants`. Attribute `ast` is
    deleted.

    Parameters
    ----------
    func : FunctionDecomposition

    Returns
    -------
    FunctionDecomposition
    """
    body, constants = separate_constants_ast(func.ast.body[0].body)
    return func.update(body=body, constants=constants)


def sort_constants(func: FunctionDecomposition):
    """Sort constants

    Sort the statements from the with constants statement such that they can be
    evaluated sequentially. The resulting FunctionDecomposition has new
    attributes `sorted_constants` and `constant_graph`. Attributes `constants`
    is deleted.

    Parameters
    ----------
    func : FunctionDecomposition

    Returns
    -------
    FunctionDecomposition
    """
    sorted_constants, constant_graph = sort_constants_ast(func.constants)
    return func.update(
        sorted_constants=sorted_constants,
        constant_graph=constant_graph,
    )


def copy_only_constants(
        func: FunctionDecomposition,
        xun_function_names=frozenset(),
    ):
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
    func : FunctionDecomposition
    xun_function_names : frozenset of str
        names of known xun functions

    Returns
    -------
    FunctionDecomposition
    """
    def gen_deepcopy_expr(expr):
        deepcopy_id = ast.Name(id='deepcopy', ctx=ast.Load())
        return ast.Call(func=deepcopy_id, args=[expr], keywords=[])

    class CallArgumentCopyTransformer(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)

            if not isinstance(node.func, ast.Name):
                return node

            if node.func.id in xun_function_names:
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
    transformed = [transformer.visit(stmt) for stmt in func.sorted_constants]

    from_copy_import_deepcopy = ast.ImportFrom(
        module='copy',
        names=[ast.alias(name='deepcopy', asname=None)],
        level=0
    )
    copy_only_constants = [from_copy_import_deepcopy, *transformed]

    return func.update(copy_only_constants=copy_only_constants)


def build_xun_graph(
        func: FunctionDecomposition,
        xun_function_names=frozenset(),
    ):
    """Build Xun Graph Transformation

    This transformation will generate code from a FunctionDecompositions
    copy_only_constants such that any call to a xun function is replaced by an
    uncopyable FutureValueNode and registered in a graph. The new code will
    return a dependency graph for the function assembled from the
    FunctionDecomposition.

    This version of the code is final and will be run during scheduling.

    Attribute `xun_graph` is introduced.

    Parameters
    ----------
    func : FunctionDecomposition
    xun_function_names : frozenset of str
        names of known xun functions

    Returns
    -------
    FunctionDecomposition
    """

    # The following code is never executed here, but is injected into the
    # FunctionDecomposition body. (`xun_graph` attribute). The injected code
    # provides a graph, and a funtion _xun_register_call that is used to
    # populate the graph.
    @function_ast
    def helper_code():
        from itertools import chain as _xun_chain
        from xun.functions import CallNode as _xun_CallNode
        from xun.functions import CallNodeSubscript as _xun_CallNodeSubscript
        import networkx as _xun_nx

        _xun_graph = _xun_nx.DiGraph()

        def _xun_register_call(fname,
                               *args,
                               **kwargs):

            dependencies = filter(
                lambda a: isinstance(a, _xun_CallNode),
                map(
                    lambda a:
                        a.call if isinstance(a, _xun_CallNodeSubscript) else a,
                    _xun_chain(args, kwargs.values())
                )
            )
            call = _xun_CallNode(fname, *args, **kwargs)
            _xun_graph.add_node(call)
            _xun_graph.add_edges_from((dep, call) for dep in dependencies)
            return call

    header = helper_code.body[0].body

    class XCall(ast.NodeTransformer):
        """
        Transformation any calls to a xun function to _xun_register_call
        """
        def __init__(self):
            self.target_shape = 0
            self.is_target_tuple = False

        def visit_Assign(self, node):
            target = node.targets[0]
            if isinstance(target, ast.Name):
                self.is_target_tuple = False
                self.target_shape = 1
            elif isinstance(target, (ast.Tuple, ast.List)):
                self.is_target_tuple = True
                self.target_shape = assignment_target_shape(target)
            return self.generic_visit(node)

        def visit_Call(self, node):
            node = self.generic_visit(node)

            if not isinstance(node.func, ast.Name):
                return node

            if node.func.id not in xun_function_names:
                return node

            register_call = ast.Call(
                func=ast.Name(id='_xun_register_call', ctx=ast.Load()),
                args=[
                    ast.Constant(node.func.id),
                    *node.args
                ],
                keywords=node.keywords,
            )
            if self.is_target_tuple:
                call_node_unpack_func = ast.Attribute(
                    value=register_call,
                    attr='unpack',
                    ctx=ast.Load(),
                )
                unpack_register_call = ast.Call(
                    func=call_node_unpack_func,
                    args=[shape_to_ast_tuple(self.target_shape)],
                    keywords=[],
                )
                return unpack_register_call
            else:
                return register_call

    return_graph = ast.Return(value=ast.Name(id='_xun_graph', ctx=ast.Load()))

    xun_graph = [
        *header,
        *(
            XCall().visit(stmt)
            if isinstance(stmt, ast.Assign) or isinstance(stmt, ast.Expr)
            else stmt
            for stmt in func.copy_only_constants
        ),
        return_graph
    ]

    return func.update(xun_graph=xun_graph)


def load_from_store(
        func: FunctionDecomposition,
        xun_function_names=frozenset()
    ):
    """Load from Store Transformation

    Transform any call to xun functions into loads from the xun store. This
    version of the function is final and will be run during execution.

    Attribute `load_from_store` is introduced

    Parameters
    ----------
    func : FunctionDecomposition
    xun_function_names : frozenset of str
        names of known xun functions

    Returns
    -------
    FunctionDecomposition
    """
    class DiscoverReferences(ast.NodeVisitor):
        def __init__(self):
            self.seen_targets = []

            for node in func.copy_only_constants:
                self.visit(node)

            self.body_external_names = body_external_names(func.body)

            self.referenced_in_body = frozenset(
                t for t in self.seen_targets if t in self.body_external_names
            )

        def visit_Assign(self, node):
            self.generic_visit(node)

            if len(node.targets) != 1:
                msg = 'Structured unpacking is not supported'
                raise NotImplementedError(msg)

            target = node.targets[0]
            if isinstance(target, ast.Name):
                self.seen_targets.append(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                inner_targets = assignment_target_names(target)
                self.seen_targets += inner_targets
            else:
                raise NotImplementedError(
                    'Unsupported target {}'.format(target)
                )

            return node
    discovered_reference = DiscoverReferences()

    def is_referenced_in_body(name):
        return name in discovered_reference.referenced_in_body

    def is_xun_call(node):
        return (
            isinstance(node, ast.Call) and
            isinstance(node.func, ast.Name) and
            node.func.id in xun_function_names
        )

    class NodeMapper(ast.NodeTransformer):
        def map(self, nodes):
            transformed = (self.visit(copy.deepcopy(node)) for node in nodes)
            return [node for node in transformed if node is not None]

    class Call2CallNode(NodeMapper):
        def __init__(self):
            self.target_shape = 0
            self.is_target_tuple = False

        def visit_Assign(self, node):
            target = node.targets[0]
            if isinstance(target, ast.Name):
                self.is_target_tuple = False
                self.target_shape = 1
            elif isinstance(target, (ast.Tuple, ast.List)):
                self.is_target_tuple = True
                self.target_shape = assignment_target_shape(target)
            return self.generic_visit(node)

        def visit_Call(self, node):
            node = self.generic_visit(node)

            if not is_xun_call(node):
                return node

            construct_call = ast.Call(
                func=ast.Name(id='_xun_CallNode', ctx=ast.Load()),
                args=[ast.Constant(node.func.id), *node.args],
                keywords=node.keywords,
            )

            if self.is_target_tuple:
                call_node_unpack_func = ast.Attribute(
                    value=construct_call,
                    attr='unpack',
                    ctx=ast.Load(),
                )
                unpack_construct_call = ast.Call(
                    func=call_node_unpack_func,
                    args=[shape_to_ast_tuple(self.target_shape)],
                    keywords=[],
                )
                return unpack_construct_call
            else:
                return construct_call

    class CallNode2Load(NodeMapper):
        def __init__(self, output_targets=[]):
            self.output_targets = output_targets

        def visit_Assign(self, node):
            introduced_names = stmt_introduced_names(node)
            if any(is_referenced_in_body(name) for name in introduced_names):
                self.output_targets.append(node.targets[0])
                return self.visit(node.value)
            return None

        def visit_Call(self, node):
            if not is_xun_call(node):
                return self.generic_visit(node)

            call_node = Call2CallNode().visit(node)

            store_accessor_load_func = ast.Attribute(
                value=ast.Name(id='_xun_store_accessor', ctx=ast.Load()),
                attr='load_result',
                ctx=ast.Load(),
            )

            store_accessor_load_call = ast.Call(
                func=store_accessor_load_func,
                args=[call_node],
                keywords=[],
            )

            return store_accessor_load_call

    # If No dependencies are referenced in the body of the function, there is
    # nothing to load
    if len(discovered_reference.referenced_in_body) == 0:
        return func.update(load_from_store=[])

    assignments = [
        node for node in func.copy_only_constants
        if isinstance(node, ast.Assign)
    ]

    call_nodes = Call2CallNode().map(assignments)

    output_targets = []
    loads = CallNode2Load(output_targets=output_targets).map(assignments)

    imports = [
        *[
            node for node in func.copy_only_constants
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ],
        ast.ImportFrom(
            module='xun.functions',
            names=[
                ast.alias(
                    name='CallNode',
                    asname='_xun_CallNode'
                ),
            ],
            level=0
        ),
        ast.ImportFrom(
            module='xun.functions.store',
            names=[
                ast.alias(
                    name='StoreAccessor',
                    asname='_xun_StoreAccessor'
                ),
            ],
            level=0
        ),
    ]

    load_function = ast.FunctionDef(
        name='_xun_load_constants',
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=[
            *imports,
            ast.Assign(
                targets=[ast.Name(id='_xun_store_accessor', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id='_xun_StoreAccessor', ctx=ast.Load()),
                    args=[ast.Name(id='_xun_store', ctx=ast.Load())],
                    keywords=[],
                ),
            ),
            *call_nodes,
            ast.Return(
                value=ast.Tuple(elts=loads, ctx=ast.Load())
            )
        ],
        decorator_list=[],
    )

    load_call = ast.Assign(
        targets=[
            ast.Tuple(
                elts=[target for target in output_targets],
                ctx=ast.Store(),
            )
        ],
        value=ast.Call(
            func=ast.Name(id='_xun_load_constants', ctx=ast.Load()),
            args=[],
            keywords=[],
        ),
    )

    lfs = [
        load_function,
        load_call,
    ]

    return func.update(load_from_store=lfs)
