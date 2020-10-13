from .. import CallNode
from .driver import Driver
import logging
import networkx as nx


logger = logging.getLogger(__name__)


class Sequential(Driver):
    """
    Does a topological sort of the graph, and runs the jobs sequentially
    """

    def run_and_store(self, call, func, store_accessor):
        resolved_call = store_accessor.resolve_call(call)
        result = func(*resolved_call.args, **resolved_call.kwargs)
        store_accessor.store_result(call, func.hash, result)

    def _exec(self, graph, entry_call, function_images, store_accessor):
        assert nx.is_directed_acyclic_graph(graph)

        schedule = list(nx.topological_sort(graph))

        for node in schedule:
            if not isinstance(node, CallNode):
                continue

            func = function_images[node.function_name]

            # Do not rerun finished jobs. For example if a workflow has been
            # stopped and resumed.
            if store_accessor.completed(node, func.hash):
                logger.info('{} already completed'.format(node))
                continue

            logger.info('Running {}'.format(node))
            try:
                self.run_and_store(node, func, store_accessor)
            except Exception as e:
                logger.error(
                    '{} failed with {}'.format(node, str(e))
                )
                raise
            logger.info('{} succeeded'.format(node))

        return store_accessor.load_result(entry_call)
