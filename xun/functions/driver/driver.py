from abc import ABC
from abc import abstractmethod
import logging


logger = logging.getLogger(__name__)


class Driver(ABC):
    """Driver

    Drivers are the classes that have the responsibility of executing programs.
    This includes scheduling the calls of the call graph and managing any
    concurrency.
    """
    @abstractmethod
    def _exec(self, graph, entry_call, function_images, store):
        pass

    def exec(self, graph, entry_call, function_images, store):
        self._exec(graph, entry_call, function_images, store)
        return store.load(entry_call)

    def __call__(self, graph, entry_call, function_images, store):
        return self.exec(graph, entry_call, function_images, store)

    @staticmethod
    def compute_and_store(callnode, func, store):
        args, kwargs = store.resolve_call_args(callnode)
        results = func(*args, **kwargs)
        results.send(None)
        results.send(store)
        while True:
            try:
                result_call, result = next(results)
                logger.debug(f'Storing result for {result_call}')
                store.store(result_call, result)
            except StopIteration as result:
                logger.debug(f'Storing result for {callnode}')
                store.store(callnode, result.value)
                return result.value
