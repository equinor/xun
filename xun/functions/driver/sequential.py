from .. import CallNode
from .driver import Driver
import logging
import networkx as nx


logger = logging.getLogger(__name__)


class Sequential(Driver):
    """
    Does a topological sort of the graph, and runs the jobs sequentially
    """

    def _exec(self,
              graph,
              entry_call,
              function_images,
              store,
              global_resources):
        assert nx.is_directed_acyclic_graph(graph)

        schedule = list(nx.topological_sort(graph))
        start_time = self.timestamp()

        for node in schedule:
            if not isinstance(node, CallNode):
                continue

            func = function_images[node.function_name]['callable']

            # Do not rerun finished jobs. For example if a workflow has been
            # stopped and resumed.
            if self.value_computed(node, store):
                logger.info('{} already completed'.format(node))
                continue

            logger.info('Running {}'.format(node))
            try:
                tags = self.create_tags(func, entry_call, node, start_time)
                self.compute_and_store(node, func, store, tags)
            except Exception as e:
                logger.error(
                    '{} failed with {}'.format(node, str(e))
                )
                raise
            logger.info('{} succeeded'.format(node))

        return store.load_callnode(entry_call)
