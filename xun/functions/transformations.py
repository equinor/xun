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
from .util import assignment_target_introduced_names
from .util import assignment_target_shape
from .util import body_external_names
from .util import flatten_assignment_targets
from .util import function_ast
from .util import indices_from_shape
from .util import prefix_load_result
from .util import separate_constants_ast
from .util import sort_constants_ast
from .xun_typing import TypeDeducer
from .xun_typing import is_iterator_type
from .xun_typing import is_list_type
from .xun_typing import is_set_type
from .xun_typing import is_tuple_type
from .xun_typing import is_xun_type
from itertools import chain
import copy
import types


class FunctionDecomposition(types.SimpleNamespace):
    """ FunctionDecomposition

    Immutable decomposition of a function. Instances of FunctionDecomposition
    are used to transform functions as represented by syntax trees.

    Methods
    -------
    apply(transform, *args, **kwargs)
        Apply transform and return a new FunctionDecomposition
    assemble(*nodes)
        Assemble FunctionDecomposition into Function object with the given
        function body ast.AST nodes
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
    ...     # Remove first return
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
            Callable that takes a FunctionDecomposition, computes new
            attributes and returns a new, updated FunctionDecomposition. This
            is typically a function of the following form::

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
            Lists of statements (in order) to be used as the statements of the
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
                    returns=None,
                    type_comment=None,
                )
            ],
        ))

        f = FunctionImage(
            fdef,
            self.desc.name,
            self.desc.qualname,
            self.desc.doc,
            self.desc.annotations,
            self.desc.module,
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
            Use with care, replaces the underlying function description

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


def deduce_types(func: FunctionDecomposition, dependencies={}):
    """Deduce types

    Deduce the type of each expression

    Parameters
    ----------
    func : FunctionDecomposition
    dependencies : mapping from str to Function
        Maps names of dependencies to their Functions

    Returns
    -------
    FunctionDecomposition
    """
    type_deducer = TypeDeducer(known_xun_functions=dependencies)

    for stmt in func.sorted_constants:
        if isinstance(stmt, ast.Assign):
            type_deducer.visit(stmt)

    return func.update(expr_name_type_map=type_deducer.expr_name_type_map,
                       with_names=type_deducer.with_names)


def copy_only_constants(func: FunctionDecomposition, dependencies={}):
    """Copy only constants

    Working on the FunctionDecomposition `sorted_constants`. Change any
    expression leaving the with constants statement through function calls to a
    copy of the expression. Change any expression entering as a result of a
    function to a copy of that expression. This ensures that any value inside
    the with constants statement never changes, e.g. acts as if it is a value,
    never a reference. This is necessary to ensure immutability in constant
    fields, and is what is responsible for the constness of the fields. If a
    function took a reference to a value instead of a copy, it could change the
    value. This would result in us not being able to evaluate and know its
    value when scheduling, since order is arbitrary.

    Calls to xun functions will later be replaced by sentinel nodes, which are
    not copyable, and should therefore not be made copy only.

    The `sorted_constants` attribute is replaced by `copy_only_constants`.

    Parameters
    ----------
    func : FunctionDecomposition
    dependencies : mapping from str to Function
        Maps names of dependencies to their Functions

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
    transformed = [transformer.visit(stmt) for stmt in func.sorted_constants]

    from_copy_import_deepcopy = ast.ImportFrom(
        module='copy',
        names=[ast.alias(name='deepcopy', asname=None)],
        level=0
    )
    copy_only_constants = [from_copy_import_deepcopy, *transformed]

    return func.update(copy_only_constants=copy_only_constants)


def unroll_unpacking_assignments(func: FunctionDecomposition):
    """Unroll To Unpacking Assignments Transformation

    For every assign statement with an iterable target with multiple variables,
    make a new assignment for each target. For those, the iterable on the right
    hand side is subscripted with the corresponding index.

    Parameters
    ----------
    func : FunctionDecomposition

    Returns
    -------
    FunctionDecomposition
    """
    unrolled_stmts = []
    for stmt in func.copy_only_constants:
        if isinstance(stmt, ast.Assign):
            if len(stmt.targets) > 1:
                raise SyntaxError("Multiple targets not supported")

            target = stmt.targets[0]
            target_shape = assignment_target_shape(target)

            if target_shape == (1,):
                unrolled_stmts.append(stmt)
                continue

            indices = indices_from_shape(target_shape)
            flatten_targets = flatten_assignment_targets(target)

            for index, target in zip(indices, flatten_targets):
                unrolled_value = stmt.value
                for i in index:
                    if isinstance(unrolled_value, (ast.Tuple, ast.List)):
                        # If the value is actually a tuple or a list, its
                        # elements will be available as elements
                        unrolled_value = unrolled_value.elts[i]
                    else:
                        expr_type = func.expr_name_type_map[target.id]
                        if is_iterator_type(expr_type) or is_set_type(
                                expr_type):
                            # Wrap in list to be able to subscript later
                            unrolled_value = ast.Call(
                                func=ast.Name(id='list', ctx=ast.Load()),
                                args=[unrolled_value],
                                keywords=[],
                            )

                        # If not, the value should be a subscriptable type
                        # and the subscripting has to happen at runtime
                        if isinstance(i, int):
                            s = ast.Index(
                                value=ast.Constant(value=i, kind=None))
                        elif isinstance(i, slice):
                            lower = i.start
                            upper = i.stop + 1 if i.stop < -1 else None
                            s = ast.Slice(
                                lower=ast.Constant(value=lower, kind=None),
                                upper=ast.Constant(value=upper, kind=None),
                                step=None,
                            )
                        else:
                            raise TypeError('Invalid content in structure')

                        unrolled_value = ast.Subscript(
                            value=unrolled_value,
                            slice=s,
                            ctx=ast.Load()
                        )

                unrolled_stmts.append(
                    ast.Assign(
                        targets=[target],
                        value=unrolled_value,
                    )
                )
        else:
            unrolled_stmts.append(stmt)

    return func.update(unrolled_stmts=unrolled_stmts)


def map_expressions(func: FunctionDecomposition):
    """Map expressions

    Map all expressions on the right hand side to the corresponding variable on
    the left hand using a dictionary. Also replace names in expressions with
    its corresponding expression.

    Parameters
    ----------
    func : FunctionDecomposition

    Returns
    -------
    FunctionDecomposition
    """

    class ReplaceSymbolicValues(ast.NodeTransformer):
        def __init__(self, unrolled_exprs_map):
            self.unrolled_exprs_map = unrolled_exprs_map

        def visit_Name(self, node):
            if node.id in self.unrolled_exprs_map:
                return self.unrolled_exprs_map[node.id]
            return self.generic_visit(node)

    unrolled_exprs_map = {}
    for stmt in func.unrolled_stmts:
        if isinstance(stmt, ast.Assign):
            unrolled_exprs_map[stmt.targets[0].id] = ReplaceSymbolicValues(
                unrolled_exprs_map).visit(stmt.value)

    return func.update(unrolled_exprs_map=unrolled_exprs_map)


def build_xun_graph(func: FunctionDecomposition, dependencies={}):
    """Build Xun Graph Transformation

    This transformation will generate code from a FunctionDecompositions
    copy_only_constants such that any call to a xun function is registered in a
    graph. The new code will return a dependency graph for the function
    assembled from the FunctionDecomposition.

    This version of the code is final and will be run during scheduling.

    Attribute `xun_graph` is introduced.

    Parameters
    ----------
    func : FunctionDecomposition
    dependencies : mapping from str to Function
        maps names of dependencies to their Functions

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
        RegisterCallWrapper().visit(copy.deepcopy(stmt))
        if isinstance(stmt, ast.Assign) or isinstance(stmt, ast.Expr)
        else stmt
        for stmt in func.unrolled_stmts
    ]

    xun_graph = [
        *header,
        *body,
        return_graph
    ]

    return func.update(xun_graph=xun_graph)


def load_from_store(func: FunctionDecomposition, dependencies={}):
    """Load from Store Transformation

    Transform any call to xun functions into loads from the xun store. This
    version of the function is final and will be run during execution.

    Attribute `load_from_store` is introduced

    Parameters
    ----------
    func : FunctionDecomposition
    dependencies : mapping from str to Function
        maps names of dependencies to their Functions

    Returns
    -------
    FunctionDecomposition
    """
    class DiscoverReferences(ast.NodeVisitor):
        def __init__(self):
            self.seen_targets = []

            for node in func.unrolled_stmts:
                self.visit(node)

            self.body_external_names = body_external_names(func.body)

            self.referenced_in_body = frozenset(
                t for t in self.seen_targets if t in self.body_external_names
            )

        def visit_Assign(self, node):
            self.generic_visit(node)
            target = node.targets[0]
            self.seen_targets.extend(
                assignment_target_introduced_names(target)
                if isinstance(target, (ast.Tuple, ast.List)) else [target.id]
            )
            return node
    discovered_reference = DiscoverReferences()

    def is_referenced_in_body(name):
        return name in discovered_reference.referenced_in_body

    # If No dependencies are referenced in the body of the function, there is
    # nothing to load
    if len(discovered_reference.referenced_in_body) == 0:
        return func.update(load_from_store=[])

    def is_xun_call(node):
        return (
            isinstance(node, ast.Call) and
            isinstance(node.func, ast.Name) and
            node.func.id in dependencies
        )

    def is_xun_callnode(node):
        return (
            isinstance(node, ast.Call) and
            isinstance(node.func, ast.Name) and
            node.func.id == '_xun_CallNode'
        )

    class Call2CallNode(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            if is_xun_call(node):
                return ast.Call(
                    func=ast.Name(id='_xun_CallNode', ctx=ast.Load()),
                    args=[
                        ast.Constant(node.func.id,
                                     kind=None),
                        ast.Constant(dependencies[node.func.id].hash,
                                     kind=None),
                        *node.args,
                    ],
                    keywords=node.keywords,
                )
            return node

    class CallNode2Load(ast.NodeTransformer):
        def __init__(self, expr_name):
            self.expr_name = expr_name

        def visit_Call(self, node):
            if is_xun_callnode(node):
                return prefix_load_result(node)
            return self.generic_visit(node)

        def visit_ListComp(self, node):
            expr_type = func.expr_name_type_map[self.expr_name]
            loaded_node = node
            if is_list_type(expr_type):
                elts_type = expr_type.__args__[0]
                if is_tuple_type(elts_type):
                    loaded_elts = []
                    for index, elt in enumerate(node.elt.elts):
                        elt_type = elts_type.__args__[index]
                        if is_xun_type(elt_type):
                            loaded_elts.append(prefix_load_result(elt))
                        else:
                            loaded_elts.append(elt)
                    loaded_node.elt = ast.Tuple(elts=loaded_elts,
                                                ctx=ast.Load())
                elif is_xun_type(elts_type):
                    loaded_node.elt = prefix_load_result(node.elt)
            else:
                if is_xun_type(expr_type):
                    loaded_node.elt = prefix_load_result(node.elt)

            return loaded_node

    loads = []
    output_targets = []
    for name in func.with_names:
        if is_referenced_in_body(name):
            output_targets.append(ast.Name(id=name, ctx=ast.Store()))
            unrolled_expr = copy.deepcopy(func.unrolled_exprs_map[name])
            callnodes = Call2CallNode().visit(unrolled_expr)
            loaded_callnodes = CallNode2Load(expr_name=name).visit(callnodes)
            loads.append(loaded_callnodes)

    imports = [
        *[
            node for node in func.unrolled_stmts
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
            level=0,
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
                type_comment=None,
            ),
            ast.Return(
                value=ast.Tuple(elts=loads, ctx=ast.Load())
            )
        ],
        decorator_list=[],
        returns=None,
        type_comment=None,
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
        type_comment=None,
    )

    lfs = [
        load_function,
        load_call,
    ]

    return func.update(load_from_store=lfs)
