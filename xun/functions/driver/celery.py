from .. import graph as graph_helpers
from .driver import Driver
import asyncio
import celery
import contextlib
import kombu
import logging
import networkx as nx


logger = logging.getLogger(__name__)


celery_app = celery.Celery('xun')
celery_app.conf.task_serializer = 'pickle'
celery_app.conf.accept_content = ['pickle']  # Ignore other content
celery_app.conf.result_serializer = 'pickle'
celery_app.conf.timezone = 'Europe/Oslo'
celery_app.conf.enable_utc = True
celery_app.conf.task_acks_late = True # Since we run on volatile infrastructure


class Celery(Driver):
    def __init__(self, broker_url=None, result_backend=None):
        self.broker_url = broker_url
        self.result_backend = result_backend

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

            # Celery apps are lazily initialized, once evaluated, it will now
            # be locked to the result backend we specify here.
            celery_app.conf.result_backend = self.result_backend

            state = AsyncCeleryState(
                pool, graph, function_images, store_accessor
            )
            return state(entry_call)


class AsyncCeleryState:
    def __init__(self, pool, graph, function_images, store_accessor):
        self.connection_pool = pool
        self.graph = graph
        self.function_images = function_images
        self.store_accessor = store_accessor
        self.succeeded = set()
        self.visited = set()
        self.error = None

    def __call__(self, entry_call):
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(self.exception_handler)
        task = loop.create_task(self.run())
        loop.run_until_complete(task)

        if self.error is not None:
            raise self.error

        return self.store_accessor.load_result(entry_call)

    def exception_handler(self, loop, context):
        if not self.error:
            self.error = context.get('exception')

    async def run(self):
        queue = asyncio.Queue()

        consumer = asyncio.ensure_future(self.consume_tasks(queue))

        for node in graph_helpers.source_nodes(self.graph):
            logger.debug(
                'Enqueuing source node {}'.format(node)
            )
            queue.put_nowait(node)
        await queue.join()

        consumer.cancel()

    async def consume_tasks(self, queue):
        while True:
            node = await queue.get()

            if self.error is not None:
                self.cancel_queue(queue, seen_node=node)
                break
            elif not self.is_ready(node):
                logger.debug('{} not ready'.format(node))
                queue.task_done()
            else:
                asyncio.ensure_future(self.execute_task(node, queue))

    async def execute_task(self, node, queue):
        try:
            assert self.is_ready(node)

            if node in self.visited:
                return
            self.visited.add(node)

            func = self.function_images[node.function_name]

            if self.store_accessor.completed(node, func.hash):
                logger.info('{} already completed'.format(node))
            else:
                logger.info('Submitting {}'.format(node))
                with self.connection_pool.acquire() as connection:
                    await celery_xun_exec.async_apply_async(
                        args=(node, func, self.store_accessor),
                        connection=connection,
                        backend='',
                    )
                logger.info('{} succeeded'.format(node))

            self.succeeded.add(node)

            for successor in self.graph.successors(node):
                logger.debug(
                    'Enqueuing {}, successor of {}'.format(successor, node)
                )
                queue.put_nowait(successor)
        except Exception as e:
            logger.error('{} failed with {}'.format(node, str(e)))
            raise
        finally:
            # Notify the task queue that a task has been completed. There is a
            # coroutine waiting for the queue to complete, so this is _very_
            # important
            queue.task_done()

    def is_ready(self, node):
        dependencies_satisfied = all(
            i in self.succeeded for i in self.graph.predecessors(node)
        )
        return dependencies_satisfied

    def cancel_queue(self, queue, seen_node=None):
        if seen_node is not None:
            logger.info(
                '{} cancelled due to previous failure'.format(seen_node)
            )
            queue.task_done()

        while not queue.empty():
            node = queue.get_nowait()
            queue.task_done()
            logger.info('{} cancelled due to previous failure'.format(node))


class AsyncTask(celery.Task):
    async def async_apply_async(self, args=None, kwargs=None, task_id=None,
                                producer=None, link=None, link_error=None,
                                shadow=None, **options):
        ar = self.apply_async(
            args, kwargs, task_id, producer, link, link_error, shadow,
            **options
        )

        while not ar.successful() and not ar.failed():
            await asyncio.sleep(0.05)

        result = ar.get()

        if isinstance(result, Exception):
            raise result

        return result


@celery_app.task(base=AsyncTask)
def celery_xun_exec(call, func, store_accessor):
    logger = celery.utils.log.get_task_logger(__name__)
    logger.info('Executing {}'.format(call))

    args, kwargs = store_accessor.resolve_call_args(call)
    result = func(*args, **kwargs)
    store_accessor.store_result(call, func.hash, result)

    logger.info('{} succeeded'.format(call))
    return 0
