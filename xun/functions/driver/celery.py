from .. import CallNode
from .. import TargetNode
from .. import graph as graph_helpers
from .driver import Driver
from .driver import replace_sentinels
import asyncio
import celery
import logging
import networkx as nx
import queue


logger = logging.getLogger(__name__)


class Celery(Driver):
    def exec(self, graph, entry_call, function_images, store):
        assert nx.is_directed_acyclic_graph(graph)
        state = AsyncState(graph, function_images, store)
        return state(entry_call)


celery_app = celery.Celery('xun', backend='rpc://')
celery_app.conf.update(
    task_serializer='pickle',
    accept_content=['pickle'],  # Ignore other content
    result_serializer='pickle',
    timezone='Europe/Oslo',
    enable_utc=True,
)


class AsyncState:
    def __init__(self, graph, function_images, store):
        self.completed = set()
        self.graph = graph
        self.function_images = function_images
        self.store = store

        # Temporary
        from ..store import Redis
        self.hack_store = Redis('localhost')

    def __call__(self, entry_call):
        source_nodes = graph_helpers.source_nodes(self.graph)
        asyncio.run(self.run_nodes(source_nodes))
        return self.hack_store[entry_call]

    async def run_nodes(self, nodes):
        tasks = []
        for coro in asyncio.as_completed([self.visit(node) for node in nodes]):
            N = await coro
            next = [node for node in N if self.is_ready(node)]
            tasks.append(self.run_nodes(next))
        await asyncio.gather(*tasks)

    async def visit(self, node):
        assert self.is_ready(node)

        if node in self.completed:
            logger.info('Skipping {}'.format(node))
            return self.graph.successors(node)

        if isinstance(node, CallNode) and node not in self.hack_store:
            logger.info('Submitting {}'.format(node))

            func = self.function_images[node.function_name]
            await celery_xun_exec.async_delay(node, func, self.store)

            logger.info('{} succeeded'.format(node))

        self.completed.add(node)
        return self.graph.successors(node)

    def is_ready(self, node):
        dependencies_satisfied = all(
            i in self.completed for i in self.graph.predecessors(node)
        )
        return dependencies_satisfied


class AsyncTask(celery.Task):
    async def async_delay(self, *args, **kwargs):
        ar = self.delay(*args, **kwargs)

        while not ar.ready() and not ar.failed():
            await asyncio.sleep(0.05)

        if isinstance(ar.result, Exception):
            raise ar.result

        return ar.result


@celery_app.task(base=AsyncTask)
def celery_xun_exec(call, func, store):
    logger = celery.utils.log.get_task_logger(__name__)
    logger.info('Executing {}'.format(call))

    call = replace_sentinels(store, call)
    result = func(*call.args, **call.kwargs)
    store[call] = result

    logger.info('{} succeeded'.format(call))
    return 0
