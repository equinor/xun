from .driver import Driver
import dask
import logging
import networkx as nx

logger = logging.getLogger(__name__)


class DaskDriverError(Exception):
    pass


def compute_proxy(node, dependencies, func, store_accessor):
    if store_accessor.completed(node):
        return store_accessor.load_result(node)

    args, kwargs = store_accessor.resolve_call_args(node)
    try:
        result = func(*args, **kwargs)
    except Exception as e:
        raise DaskDriverError(f'task {node} failed') from e
    except:
        raise ValueError('???')
    store_accessor.store_result(node, result)
    return node


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

        e = future.exception()
        if e:
            raise DaskDriverError('Job failed') from e
        return future.result()
