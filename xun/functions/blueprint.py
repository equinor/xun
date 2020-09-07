from .errors import NotDAGError
from .graph import CallNode
from .graph import TargetNameNode
from .graph import sink_nodes
import networkx as nx
import queue


class Blueprint:
    def __init__(self, func, *args, **kwargs):
        self.call = CallNode(func.name, *args, **kwargs)
        self.functions = discover_functions(func)
        self.graph = build_call_graph(self.functions, self.call)

    def run(self, driver=None, store=None):
        if driver is None:
            raise ValueError("driver must be specified")
        if store is None:
            raise ValueError("store must be specified")

        function_images = {
            name: func.callable(extra_globals={'_xun_store': store})
            for name, func in self.functions.items()
        }

        # Make sure that everything given to the driver is pickleable
        if __debug__:
            import pickle
            pickle.dumps(self.graph)
            pickle.dumps(self.call)
            pickle.dumps(function_images)
            pickle.dumps(store)

        return driver.exec(self.graph, self.call, function_images, store)


def discover_functions(root_function):
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
    func = functions[call.function_name]
    graph = func.graph(*call.args, **call.kwargs)

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

    graph.add_node(call)
    graph.add_edges_from(
        (node, call) for node in sink_nodes(graph) if node != call
    )

    if not nx.is_directed_acyclic_graph(graph):
        raise NotDAGError()

    dependencies = tuple(
        n for n in graph.nodes if isinstance(n, CallNode) and n != call
    )

    return graph, dependencies


def build_call_graph(functions, call):
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
    graph, dependencies = build_function_call_graph(functions, call)

    q = queue.Queue()
    visited = {call}

    for call in dependencies:
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
            raise NotDAGError()

    return graph
