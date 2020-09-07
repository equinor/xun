from .. import CallNode
from .. import FutureValueNode
from .driver import Driver
from .driver import replace_futures
import networkx as nx


class Sequential(Driver):
    """
    Does a topological sort of the graph, and runs the jobs sequentially
    """

    def run_and_store(self, call, function_images, store):
        func = function_images[call.function_name]
        resolved_call = replace_futures(store, call)
        result = func(*resolved_call.args, **resolved_call.kwargs)
        store[FutureValueNode(call)] = result

    def exec(self, graph, entry_call, function_images, store):
        assert nx.is_directed_acyclic_graph(graph)

        schedule = list(nx.topological_sort(graph))

        for task in schedule:
            if not isinstance(task, CallNode):
                continue

            # Do not rerun finished jobs. For example if a workflow has been
            # stopped and resumed.
            if task in store:
                continue

            self.run_and_store(task, function_images, store)

        return store[FutureValueNode(entry_call)]
