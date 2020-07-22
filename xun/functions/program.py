from . import transformations
from .function_image import FunctionImage
from .functions import NotDAGError
from .functions import overwrite_globals
import ast
import networkx as nx
import queue
import types


class Compiler:
    """Compiler

    Helper class to build programs. Compiler instances are created from contexts

    Attributes
    ----------
    context : xun.context
        The context that created this compiler
    entry_name : str
        Name of the context function that will be used as entrypoint in the
        output program

    See Also
    --------
    xun.context : for examples on how to create programs from contexts
    """
    def __init__(self, context, entry_name):
        self.context = context
        self.entry_name = entry_name

    def compile(self, *args, **kwargs):
        """Compile

        Builds a runnable program from our entry point and the provided
        arguments.

        Returns
        -------
        Program
            A program ready to be executed
        """
        call = CallNode(self.entry_name, *args, **kwargs)
        graph = build_call_graph(self.context, call)
        functions = build_functions(self.context)
        return Program(
            self.context.driver,
            self.context.store,
            graph,
            functions,
            call
        )


class Program:
    """Program

    Callable program with everything needed to execute a workflow.

    Attributes
    ----------
    driver : xun.functions.driver.Driver
        The driver that will execute programs compiled from this context
    store : xun.functions.store.Store
        The store that to be used when executing programs
    graph : nx.DiGraph
        The call dependency graph used to schedule the execution of this program
    functions : Mapping from str to xun.functions.Function
        Serializable function representations to be run by this program
    entry_call : CallNode
        The call that will be executed by this program
    """
    def __init__(self, driver, store, graph, functions, entry_call):
        self.driver = driver
        self.store = store
        self.graph = graph
        self.functions = functions
        self.entry_call = entry_call

    def __call__(self):
        return self.driver(self)

    def __getitem__(self, key):
        return self.functions.__dict__[key]


class CallNode:
    """CallNode

    Representaion of a call that is to be executed. These are used to represent
    entry points, the calls in the call graph, and are the keys used in the
    store. When a call is executed, the result is stored in the program store
    using the CallNode as key.

    Attributes
    ----------
    function_name : str
        name of the function this representation is a call to
    args : lists of arguments
        the arguments of this call
    kwargs : mapping of str to arguments
        the keyword arguments of this call
    """
    def __init__(self, function_name, *args, **kwargs):
        self.function_name = function_name
        self.args = args
        self.kwargs = kwargs

    def __eq__(self, other):
        try:
            return (self.function_name == other.function_name
                and self.args == other.args
                and self.kwargs == other.kwargs)
        except AttributeError:
            return False

    def __hash__(self):
        return hash((
            self.function_name,
            tuple(self.args),
            tuple(self.kwargs.items())
        ))

    def __repr__(self):
        args = []
        if len(self.args) > 0:
            args.append(', '.join(repr(a) for a in self.args))
        if len(self.kwargs) > 0:
            args.append(', '.join(
                '{}={}'.format(k, v) for k, v in self.kwargs.items()
            ))
        return 'CallNode<{}({})>'.format(self.function_name, ', '.join(args))


class SentinelNode:
    """SentinelNode

    This node serves two purposes, they are used as sentinel nodes representing
    future values in the call graph. And are used as guards when building the
    call graph. When the call graph is built, the functions doing the building
    will use sentinel nodes as representations for values returned by context
    functions. This makes let's us use the sentinel nodes directly in the
    function dependency graph.

    Another use is that because sentinel nodes are not copyable, and arguments
    and results to and from call to functions outside the context are copied,
    they cannot be used for anything other than as arguments to other context
    functions. This guards against attempted changes to future values, something
    that is of course impossible.

    Attributes
    ----------
    call : CallNode
        The CallNode whos result this Node represents
    """
    def __init__(self, call):
        self.call = call

    def __copy__(self):
        raise _xun_CopyError('Cannot copy value')

    def __deepcopy__(self, memo=None):
        raise _xun_CopyError('Cannot copy value')

    def __eq__(self, other):
        try:
            return self.call == other.call
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.call)

    def __repr__(self):
        return 'SentinelNode<{}>'.format(self.call)


class TargetNode:
    """TargetNode

    Targets are the results of assignments in with constant statements. Given
    the following client code::

        @context.function()
        def job(sentinel_node1, sentinel_node2, some_argument):
            return some_computation(target2, target3, some_argument)
            with ...:
                target1 = some_context_function(sentinel_node1)
                target2 = some_context_function(sentinel_node2)
                target3 = some_other_context_function(target1)

    will produce the following call graph
    assuming
        call_node = CallNode<job(sentinel_node1, sentinel_node2, some_argument)>

    G
    |
    * sentinel_node1
    |
    * CallNode<some_context_function(sentinel_node1)>
    |
    * TargetNode(name=target1, owner=call_node)
    |
    * CallNode<some_other_context_function(target1)>
    |
    * TargetNode(name=target3, owner=call_node)
    |
    | G
    | |
    | * sentinel_node2
    | |
    | * CallNode<some_other_context_function(sentinel_node2)
    | |
    | * TargetNode(name=target2, owner=call_node)
    |/
    * call_node
    |
    G


    Attributes
    ----------
    name : str
        name of the target
    other : CallNode
        The call owning this target
    """
    def __init__(self, name, owner):
        self.name = name
        self.owner = owner

    def __eq__(self, other):
        try:
            return self.name == other.name and self.owner == other.owner
        except AttributeError:
            return False

    def __hash__(self):
        return hash((self.name, self.owner))

    def __repr__(self):
        return 'TargetNode(name={}, owner={})'.format(self.name, self.owner)


class TargetNameNode:
    """TargetNameNode

    Temporary target node used before it is converted to a TargetNode. This
    node is only aware of it's name, but not of it's owner

    Attributes
    ----------
    target_name : str
        The name of the target this node represents

    See Also
    --------
    TargetNode
    """
    def __init__(self, name):
        self.target_name = name

    def __eq__(self, other):
        try:
            return self.target_name == other.target_name
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.target_name)

    def __repr__(self):
        return 'TargetNameNode(target_name={})'.format(self.target_name)

    def to_target_node(self, owner):
        """To target node

        Create a full TargetNode from this node

        Parameters
        ----------
        owner : CallNode
            The call node that owns the TargetNode

        Returns
        -------
        TargetNode
            The full TargetNode this TargetNameNode should become
        """
        return TargetNode(self.target_name, owner)


def build_function_graph(context, call):
    """Build Function Graph

    Given a context and a call, build the internal dependency graph for the
    given call.

    Parameters
    ----------
    context : xun.context
        The context this graph is produced from
    call : CallNode
        The call node this sub-graph is built for

    Returns
    -------
    nx.DiGraph, tuple of CallNode
        the internal dependency graph and calls this call depend on
    """
    def skip_xun_functions(node):
        return isinstance(node.func, ast.Name) and node.func.id in context

    decomposed = (FunctionImage(context[call.function_name])
        .apply(transformations.separate_constants)
        .apply(transformations.sort_constants)
        .apply(transformations.copy_only_constants,
               ignore_predicate=skip_xun_functions)
        .apply(transformations.build_xun_graph, context)
    )

    graph_builder = decomposed.assemble(decomposed.xun_graph).compile()
    graph = graph_builder(*call.args, **call.kwargs)

    # The compiled functions does not know it self, so it cannot return
    # TargetNodes. Instead, it returns TargetNameNodes, which need to be
    # converted
    graph = nx.relabel_nodes(
        graph,
        {
            t: t.to_target_node(call)
            for t in graph.nodes
            if isinstance(t, TargetNameNode)
        },
    )

    graph.add_edges_from((node, call) for node in sink_nodes(graph))

    if not nx.is_directed_acyclic_graph(graph):
        raise NotDAGError()

    dependencies = tuple(
        n for n in graph.nodes if isinstance(n, CallNode) and n != call
    )

    return graph, dependencies


def build_call_graph(context, call):
    """Build Call Graph

    Build the program call graph by doing a breadth-first search, starting at
    the entry call and discovering the call graph as find function dependencies.

    Parameters
    ----------
    context : xun.context
        The context this graph is built from
    call : CallNode
        The program entry point that the graph will be built from

    Returns
    -------
    nx.DiGraph
        The call graph built from the context and entry call. The resulting
        graph is required to be a directed acyclic graph.
    """
    graph, dependencies = build_function_graph(context, call)

    q = queue.Queue()
    visited = {call}

    for call in dependencies:
        q.put(call)

    while not q.empty():
        call = q.get()

        assert isinstance(call, CallNode)

        if call in visited:
            continue

        func_graph, dependencies = build_function_graph(context, call)

        for dependency in dependencies:
            q.put(dependency)

        graph = nx.compose(graph, func_graph)

        if not nx.is_directed_acyclic_graph(graph):
            raise NotDAGError()

    return graph


def sink_nodes(dag):
    """
    Given a directed acyclic graph, return a list of it's sink nodes.
    """
    if __debug__ and not nx.is_directed_acyclic_graph(dag):
        raise ValueError('dag must be directed acyclic graph')
    return [n for n, out_degree in dag.out_degree() if out_degree == 0]


def build_function(context, func):
    """Build serializable Function representations

    Given the description of a context function, sort and make constants copy
    only. Move constants to the top of the function body. Replace any context
    function calls within the with constants statement with loads from store.
    Asembles the final `Function` with constants first, and body after. A
    refernece to the context store is injected into the globals of the function.
    This injection is the reason stores must be pickleable.

    Parameters
    ----------
    context : xun.context
        The context owning the function
    func : xun.functions.FunctionImage
        Description of the function to be built

    Returns
    -------
    xun.functions.Function
        The final representation of the function
    """
    def skip_xun_functions(node):
        return isinstance(node.func, ast.Name) and node.func.id in context

    fimg = (FunctionImage(func)
        .apply(transformations.separate_constants)
        .apply(transformations.sort_constants)
        .apply(transformations.copy_only_constants,
               ignore_predicate=skip_xun_functions)
        .apply(transformations.load_from_store, context)
    )

    new_desc = fimg.desc._replace(globals={
        **fimg.desc.globals,
        '_xun_store': context.store
    })
    fimg = fimg.update([], {}, new_desc=new_desc)

    f = fimg.assemble(fimg.load_from_store, fimg.body)

    return f



def build_functions(context):
    """Build functions

    Create serializable Function representations of all the context functions.

    Parameters
    ----------
    context : xun.context
        the context owning the functions

    Returns
    -------
    types.SimpleNamespace
        Namespace mapping all the Function representations

    See Also
    --------
    build_function : for a description of the transformations applied to the
        functions
    """
    functions = {}
    for fname, desc in context.functions.items():
        if fname in functions:
            raise ValueError('{} already exists'.format(fname))
        functions[fname] = build_function(context, desc)
    return types.SimpleNamespace(**functions)
