from .. import CallNode
from .. import graph as graph_helpers
from .driver import Driver
import asyncio
import celery
import contextlib
import kombu
import logging
import networkx as nx


logger = logging.getLogger(__name__)


class Celery(Driver):
    def __init__(self, broker_url=None):
        self.broker_url = broker_url

    @contextlib.contextmanager
    def connection_pool(self):
        def log_connection_error(exc, interval):
            logger.error(
                'Connection to broker {} failed with {}. Trying again in {} '
                'seconds'
                .format(self.broker_url, repr(exc), interval)
            )
        connection = kombu.Connection(
            self.broker_url,
            heartbeat=2.0,
            connect_timeout=1.0,
        )
        connection.ensure_connection(
            errback=log_connection_error,
            max_retries=3,
            interval_start=1.0,
            interval_step=2.0,
            interval_max=30.0,
            callback=None,
            reraise_as_library_errors=True,
            timeout=None
        )

        yield connection.Pool()

        connection.release()

    def _exec(self, graph, entry_call, function_images, store_accessor):
        assert nx.is_directed_acyclic_graph(graph)
        with self.connection_pool() as pool:
            state = AsyncState(
                pool, graph, function_images, store_accessor
            )
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
    def __init__(self, pool, graph, function_images, store_accessor):
        self.connection_pool = pool
        self.graph = graph
        self.function_images = function_images
        self.store_accessor = store_accessor
        self.completed = set()

    def __call__(self, entry_call):
        source_nodes = graph_helpers.source_nodes(self.graph)
        asyncio.run(self.run_nodes(source_nodes))
        return self.store_accessor.load_result(entry_call)

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
            return self.graph.successors(node)

        if isinstance(node, CallNode):
            func = self.function_images[node.function_name]

            if not self.store_accessor.completed(node, func.hash):
                logger.info('Submitting {}'.format(node))

                try:
                    with self.connection_pool.acquire() as connection:
                        await celery_xun_exec.async_apply_async(
                            args=(node, func, self.store_accessor),
                            connection=connection
                        )
                except Exception as e:
                    logger.error(
                        '{} failed with {}'.format(node, str(e))
                    )
                    raise

                logger.info('{} succeeded'.format(node))
            else:
                logger.info('{} already completed'.format(node))

        self.completed.add(node)
        return self.graph.successors(node)

    def is_ready(self, node):
        dependencies_satisfied = all(
            i in self.completed for i in self.graph.predecessors(node)
        )
        return dependencies_satisfied


class AsyncTask(celery.Task):
    async def async_apply_async(self, args=None, kwargs=None, task_id=None,
                                producer=None, link=None, link_error=None,
                                shadow=None, **options):
        ar = self.apply_async(
            args, kwargs, task_id, producer, link, link_error, shadow,
            **options
        )

        while not ar.ready() and not ar.failed():
            await asyncio.sleep(0.05)

        if isinstance(ar.result, Exception):
            raise ar.result

        return ar.result

    async def delay_async(self, *args, **kwargs):
        ar = self.delay(*args, **kwargs)

        while not ar.ready() and not ar.failed():
            await asyncio.sleep(0.05)

        if isinstance(ar.result, Exception):
            raise ar.result

        return ar.result


@celery_app.task(base=AsyncTask)
def celery_xun_exec(call, func, store_accessor):
    logger = celery.utils.log.get_task_logger(__name__)
    logger.info('Executing {}'.format(call))

    resolved_call = store_accessor.resolve_call(call)
    result = func(*resolved_call.args, **resolved_call.kwargs)
    store_accessor.store_result(call, func.hash, result)

    logger.info('{} succeeded'.format(call))
    return 0
