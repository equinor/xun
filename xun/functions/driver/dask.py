from .. import graph as graph_helpers
from .driver import Driver
import asyncio
import functools
import logging
import networkx as nx


logger = logging.getLogger(__name__)


class DaskDriverError(Exception):
    pass


class Dask(Driver):
    def __init__(self, client):
        self.client = client

    def _exec(self, graph, entry_call, function_images, store_accessor):
        assert nx.is_directed_acyclic_graph(graph)
        scheduler = DaskSchedule(self.client, function_images, store_accessor)
        return scheduler(entry_call, graph)


def compute_proxy(store_accessor, func):
    """Dask 'handles' functools.partial so that we can't use it. Create a new
       function instead."""
    def λ(node):
        args, kwargs = store_accessor.resolve_call_args(node)
        result = func(*args, **kwargs)
        store_accessor.store_result(node, result)
        return node
    functools.update_wrapper(λ,  func)
    return λ


class DaskSchedule:
    """
    Traverse the call graph and submit jobs using an async implementation of
    Kahn's algorithm [1].

    .. [1] https://en.wikipedia.org/wiki/Topological_sorting#Kahn's_algorithm
    """

    def __init__(self,
                 client,
                 function_images,
                 store_accessor):
        self.client = client
        self.function_images = function_images
        self.store_accessor = store_accessor

    def __call__(self, entry_call, graph):
        self.client.sync(self.run, graph)
        return self.store_accessor.load_result(entry_call)

    async def run(self, graph):
        atomic_graph = GraphLock(graph)
        queue = asyncio.Queue()

        consumer = asyncio.ensure_future(self.consume_tasks(atomic_graph,
                                                            queue))

        async with atomic_graph as G:
            source_nodes = graph_helpers.source_nodes(G)
        for node in source_nodes:
            logger.debug(f'Enqueuing {node}')
            queue.put_nowait(node)
        await queue.join()

        consumer.cancel()

    async def consume_tasks(self, atomic_graph, queue):
        while True:
            node = await queue.get()
            asyncio.ensure_future(self.visit(node, atomic_graph, queue))

    async def visit(self, node, atomic_graph, queue):
        try:
            if self.store_accessor.completed(node):
                logger.info(f'{node} already completed')
            else:
                logger.info(f'Submitting {node}')

                func = compute_proxy(self.store_accessor,
                                     self.function_images[node.function_name])

                future = self.client.submit(func, node)
                await self.client.gather(future, asynchronous=True)
        except Exception as e:
            logger.error(f'{node} failed with {str(e)}')
            await self.cancel_descendants(atomic_graph, node)
        else:
            logger.info(f'{node} succeeded')
            async with atomic_graph as G:
                successors = list(G.successors(node))
                G.remove_node(node)
                for s in successors:
                    if G.in_degree(s) == 0:
                        logger.debug(f'Enqueuing {s}, successor of {node}')
                        queue.put_nowait(s)
        finally:
            # Notify the task queue that a task has been completed. There is a
            # coroutine waiting for the queue to complete, so this is _very_
            # important
            queue.task_done()

    async def cancel_descendants(self, atomic_graph, node):
        async with atomic_graph as G:
            descendants = nx.algorithms.dag.descendants(G, node)
            G.remove_node(node)
            for descendant in descendants:
                G.remove_node(descendant)
                logger.error(f'{node} cancelled due to failed dependency')


class GraphLock:
    def __init__(self, value):
        self.value = value
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        await self.lock.acquire()
        return self.value

    async def __aexit__(self, *exc):
        self.lock.release()
        return not any(exc)
