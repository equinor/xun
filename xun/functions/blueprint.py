from .errors import NotDAGError
from .graph import CallNode
from .graph import TargetNameOnlyNode
from .graph import sink_nodes
import networkx as nx
import queue


class Blueprint:
    """Blueprint

    Blueprints are prepared calls to xun functions that can be executed when
    provided with a driver and a store. Blueprints comprise the call graph to
    execute, the xun functions necessary to execute the graph, and the call. In
    other words, a blueprint is the plan you want to put into action

    Methods
    -------
    run(driver, store)
        Executes the blueprint with the given driver and store

    See Also
    --------
    Function : xun function
    """

    def __init__(self, func, *args, **kwargs):
        self.call = CallNode(func.name, *args, **kwargs)
        self.functions = discover_functions(func)
        self.graph = build_call_graph(self.functions, self.call)

    def run(self, driver=None, store=None):
        """run

        Executes this blueprint given a driver and store

        Parameters
        ----------
        driver : Driver
        store : Store

        Returns
        -------
        Any
            The result of the execution
        """
        if driver is None:
            raise ValueError("driver must be specified")
        if store is None:
            raise ValueError("store must be specified")

        function_images = {
            name: func.callable(extra_globals={'_xun_store': store})
            for name, func in self.functions.items()
        }

        # Make sure that everything given to the driver is picklable
        if __debug__:
            import pickle
            pickle.dumps(self.graph)
            pickle.dumps(self.call)
            pickle.dumps(function_images)
            pickle.dumps(store)

        return driver.exec(self.graph, self.call, function_images, store)


def discover_functions(root_function):
    """Discover Functions

    Recursivly find all dependencies of the given function.

    Parameters
    ----------
    root_function : Function
        The function to start the dependency search from

    Returns
    -------

    """
    discovered = set()

    q = queue.Queue()
    q.put(root_function)

    while not q.empty():
        current = q.get()

        if current in discovered:
            continue

        discovered.add(current)

        for dependency in current.dependencies.values():
            q.put(dependency)

    return {f.name: f for f in discovered}


def build_function_call_graph(functions, call):
    """Build Function Graph

    Given a function and a call, build the internal dependency graph for the
    given call

    Parameters
    ----------
    function : Function
        The `Function` this call graph is based on
    call : CallNode
        The call node

    Returns
    -------
    nx.DiGraph, tuple of CallNode
        the internal dependency graph and calls this call depends on
    """
    func = functions[call.function_name]
    graph = func.graph(*call.args, **call.kwargs)

    # The compiled function does not know itself, so it cannot return
    # TargetNodes. Instead, it returns TargetNameOnlyNodes, which need to be
    # converted
    graph = nx.relabel_nodes(
        graph,
        {
            t: t.to_target_node(call)
            for t in graph.nodes
            if isinstance(t, TargetNameOnlyNode)
        },
    )

    # Connect the function call graph to this call
    graph.add_node(call)
    graph.add_edges_from(
        (node, call) for node in sink_nodes(graph) if node != call
    )

    if not nx.is_directed_acyclic_graph(graph):
        raise NotDAGError

    dependencies = tuple(
        n for n in graph.nodes if isinstance(n, CallNode) and n != call
    )

    return graph, dependencies


def build_call_graph(functions, call):
    """Build Call Graph

    Build the program call graph by doing a breadth-first search, starting at
    the entry call and discovering the call graph as find function
    dependencies.

    Parameters
    ----------
    function : Function
        The `Function` this call graph is based on
    call : CallNode
        The program entry point that the graph will be built from

    Returns
    -------
    nx.DiGraph
        The call graph built from the context and entry call. The resulting
        graph is required to be a directed acyclic graph.
    """
    graph = nx.DiGraph()
    visited = set()
    q = queue.Queue()
    q.put(call)

    while not q.empty():
        call = q.get()

        if call in visited:
            continue

        visited.add(call)

        func_graph, dependencies = build_function_call_graph(functions, call)

        for dependency in dependencies:
            q.put(dependency)

        graph = nx.compose(graph, func_graph)

        if not nx.is_directed_acyclic_graph(graph):
            raise NotDAGError

    return graph
