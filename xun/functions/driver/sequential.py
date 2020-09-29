from .. import CallNode
from .driver import Driver
import networkx as nx


class Sequential(Driver):
    """
    Does a topological sort of the graph, and runs the jobs sequentially
    """

    def run_and_store(self, call, func, store_accessor):
        args, kwargs = store_accessor.resolve_call_args(call)
        result = func(*args, **kwargs)
        store_accessor.store_result(call, func.hash, result)

    def _exec(self, graph, entry_call, function_images, store_accessor):
        assert nx.is_directed_acyclic_graph(graph)

        schedule = list(nx.topological_sort(graph))

        for task in schedule:
            if not isinstance(task, CallNode):
                continue

            func = function_images[task.function_name]

            # Do not rerun finished jobs. For example if a workflow has been
            # stopped and resumed.
            if store_accessor.completed(task, func.hash):
                continue

            self.run_and_store(task, func, store_accessor)

        return store_accessor.load_result(entry_call)
