from .. import graph as graph_helpers
from ..errors import ComputeError
from .driver import Driver
import asyncio
import contextlib
import functools
import logging
import networkx as nx


logger = logging.getLogger(__name__)


class DaskDriverError(Exception):
    pass


class Dask(Driver):
    def __init__(self, client):
        self.client = client

    def _exec(self,
              graph,
              entry_call,
              function_images,
              store,
              global_resources):
        assert nx.is_directed_acyclic_graph(graph)
        scheduler = DaskSchedule(self.client,
                                 function_images,
                                 store,
                                 global_resources)
        return scheduler(entry_call, graph)


def compute_proxy(store, func):
    """Dask 'handles' functools.partial so that we can't use it. Create a new
       function instead."""
    def λ(node):
        Driver.compute_and_store(node, func, store)
        return node
    functools.update_wrapper(λ, func)
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
                 store,
                 global_resources):
        self.client = client
        self.function_images = function_images
        self.store = store
        self.errored = False
        self.futures = {}
        self.semaphores = {
            resource_name: asyncio.BoundedSemaphore(available)
            for resource_name, available in global_resources.items()
        }

    def __call__(self, entry_call, graph):
        try:
            # Run async regardless of client state
            # https://distributed.dask.org/en/latest/asynchronous.html
            self.client.sync(self.run, graph)
        except KeyboardInterrupt:
            for node, future in self.futures.items():
                logger.debug(f'{node} cancelled due to keyboard interrupt')
                future.cancel(force=True)
            raise
        if not self.errored:
            return self.store.load_callnode(entry_call)
        raise ComputeError('One or more jobs failed')

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
            if Driver.value_computed(node, self.store):
                logger.info(f'{node} already completed')
            else:
                async with contextlib.AsyncExitStack() as stack:
                    func_img = self.function_images[node.function_name]

                    semaphores = [
                        stack.enter_async_context(self.semaphores[res])
                        for res, req in func_img['global_resources'].items()
                        for _ in range(req)
                    ]
                    if semaphores:
                        logger.info(f'Acquiring resources for {node}')
                        await asyncio.gather(*semaphores)

                    logger.info(f'Submitting {node}')
                    func = compute_proxy(self.store, func_img['callable'])
                    kwargs = {}
                    for res, value in (func_img['worker_resources'].items()):
                        kwargs.setdefault('resources', {})[res] = value
                    future = self.client.submit(func, node, **kwargs)
                    self.futures[node] = future
                    await self.client.gather(future, asynchronous=True)
        except Exception as e:
            self.errored = True
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
                logger.info(
                    f'{descendant} cancelled due to failed dependency')


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
