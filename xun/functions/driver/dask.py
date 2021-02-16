from .driver import Driver
import dask
import logging
import networkx as nx

logger = logging.getLogger(__name__)


def compute_proxy(node, dependencies, func, store_accessor):
    if store_accessor.completed(node, func.hash):
        return store_accessor.load_result(node)

    args, kwargs = store_accessor.resolve_call_args(node)
    result = func(*args, **kwargs)
    store_accessor.store_result(node, func.hash, result)
    return result


class Dask(Driver):
    def __init__(self, client):
        self.client = client

    def _exec(self, graph, entry_call, function_images, store_accessor):
        assert nx.is_directed_acyclic_graph(graph)

        output = {}

        topsort = list(nx.topological_sort(graph))

        for node in topsort:
            logger.info('Submitting node {}'.format(node))
            func = function_images[node.function_name]
            dependencies = [output[anc] for anc in graph.predecessors(node)]
            output[node] = dask.delayed(compute_proxy)(node, dependencies,
                                                       func, store_accessor)

        logger.info('Running dask job')
        future = self.client.compute(output[entry_call], optimize_graph=False)
        return future.result()
