from .. import CallNode
from .driver import Driver
from .driver import replace_sentinels
import networkx as nx


class Sequential(Driver):
    """
    Does a topological sort of the graph, and runs the jobs sequentially
    """

    def run_and_store(self, call, function_images, store):
        func = function_images[call.function_name]
        result = func(*call.args, **call.kwargs)
        store[call] = result

    def exec(self, graph, entry_call, function_images, store):
        assert nx.is_directed_acyclic_graph(graph)

        schedule = list(nx.topological_sort(graph))

        for task in schedule:
            if not isinstance(task, CallNode):
                continue

            call = replace_sentinels(store, task)

            # Do not rerun finished jobs. For example if a workflow has been
            # stopped and resumed.
            if call in store:
                continue

            self.run_and_store(call, function_images, store)

        return store[entry_call]
