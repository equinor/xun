"""
This is a collection of functions used by generated code in xun runtime.
Loading and exploration of symbolic values is done through deepcopy.

The reason deepcopy is used for this is that it provides a reliable way to go
deeply into python objects. For example imagine you have a list of objects,
some of those objects contain values you would like to replace.
"""


from .errors import CopyError
from .function import SymbolicFunction
from .graph import CallNode
from .util import make_hashable
from copy import deepcopy
from itertools import count
from itertools import islice
from types import SimpleNamespace
import contextvars
import networkx as nx


def pass_by_value(func, *args, **kwargs):
    """
    This function is used in generated xun code to ensure that function calls
    in xun definitions statements (with ...:) are immutable. Additionally any
    call to a xun function is returned as symbolic callnodes.
    """
    if isinstance(func, SymbolicFunction):
        # Note that we don't deepcopy the arguments to the call node. This is
        # because we know that construction of a call node is immutable.
        return func.callnode(*args, **kwargs)
    else:
        try:
            args = deepcopy(args)
            kwargs = deepcopy(kwargs)
            result = func(*args, **kwargs)

            # Make the return type hashable, so that calls to functions like
            # `dict.items` return picklable types.
            return deepcopy(make_hashable(result))
        except CopyError as e:
            copy_error = e
        sym_name = copy_error.function_name
        arglist = [repr(arg) for arg in copy_error.args]
        arglist.extend(f'{k}={repr(v)}' for k, v in copy_error.kwargs.items())
        msg = (f'A non xun function [{func.__name__}] was passed a symbolic '
               f'value [{sym_name}({", ".join(arglist)})]')
        raise TypeError(msg)


def load_results_by_deepcopy(store_accessor, *objects):
    """
    In a local context, set the behavior of deepcopy of CallNode objects to
    load their corresponding results from the store. Return a copy of the given
    object list such that any callnode instances are replaced with their
    results.

    See Also
    --------
    xun.functions.graph.CallNode._deepcopy_context :
        value governing behavior of deepcopy of CallNode instances.
    """
    def deepcopy_impl(callnode, memo):
        yield store_accessor.load_result(callnode)

    ctx = contextvars.copy_context()
    ctx.run(CallNode._deepcopy_context.value.set, deepcopy_impl)
    return ctx.run(deepcopy, tuple(objects))


def resolve_args_by_deepcopy(store_accessor, **arguments):
    """
    Does the same as `load_results_by_deepcopy`, but in addition provides a
    namespace with the original values (callnodes included). This is used in
    yield statements inside xun functions, so that they can yield to signatures
    matching that of the owning function even if the arguments are symbolic
    (callnodes).

    See Also
    --------
    xun.functions.graph.CallNode._deepcopy_context :
        value governing behavior of deepcopy of CallNode instances.
    """
    def deepcopy_impl(callnode, memo):
        yield store_accessor.load_result(callnode)

    ctx = contextvars.copy_context()
    ctx.run(CallNode._deepcopy_context.value.set, deepcopy_impl)
    loaded = ctx.run(deepcopy, tuple(arguments.values()))

    return (*loaded, SimpleNamespace(**arguments))


def detect_dependencies_by_deepcopy(*objects):
    """
    In a local context, set the behavior of deepcopy of CallNode objects such
    that copys build a dependency graph in an indirect depth first search.

    See Also
    --------
    xun.functions.graph.CallNode._deepcopy_context :
        value governing behavior of deepcopy of CallNode instances.
    """
    graph = nx.DiGraph()

    depth_first_search_ctx = contextvars.ContextVar('depth_first_search_ctx')

    def deepcopy_impl(current_callnode, memo):
        outer_callnode, = depth_first_search_ctx.get()

        # We are dependent on the callnode it self, not a subscript of it.
        current_callnode = current_callnode._replace(subscript=())

        graph.add_node(current_callnode)
        if outer_callnode is not None:
            graph.add_edge(current_callnode, outer_callnode)

        next_context = contextvars.copy_context()
        next_context.run(depth_first_search_ctx.set, (current_callnode,))

        # Note that memo is reset for recursive calls so that deepcopy doesn't
        # skip visiting nodes it's seen. (Required to establish the edge)
        args = next_context.run(deepcopy, current_callnode.args, memo=None)
        kwargs = next_context.run(deepcopy, current_callnode.kwargs, memo=None)

        yield current_callnode._replace(args=args, kwargs=kwargs)

    ctx = contextvars.copy_context()
    ctx.run(CallNode._deepcopy_context.value.set, deepcopy_impl)
    ctx.run(depth_first_search_ctx.set, (None,))

    for obj in objects:
        ctx.run(deepcopy, obj)

    return graph


def unpack(shape, obj):
    def split_tuple(t: tuple, delimiter):
        delim_index = t.index(delimiter) if delimiter in t else None
        head = t[:delim_index]
        tail = t[delim_index + 1:] if delim_index is not None else ()
        return head, tail, delim_index

    def λ(shape, indices):
        for s in shape:
            if isinstance(s, int):
                yield from (obj[idx] for idx in islice(indices, s))
            elif isinstance(s, tuple):
                yield unpack(s, obj[next(indices)])
            else:
                raise RuntimeError(f'Invalid shape {s}')

    try:
        obj = list(obj)
    except TypeError:
        pass

    shape_head, shape_tail, ellipsis_index = split_tuple(shape, Ellipsis)
    head_indices = count()
    yield from tuple(λ(shape_head, head_indices))
    if ellipsis_index is not None:
        tail_indices = count(-1, -1)
        tail = tuple(λ(shape_tail[::-1], tail_indices))
        starred_start = next(head_indices)
        starred_end = next(tail_indices) + 1
        starred_slice = slice(starred_start, starred_end if tail else None)
        yield obj[starred_slice]
        yield from reversed(tail)
