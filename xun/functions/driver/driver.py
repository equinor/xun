from ..errors import XunInterfaceError
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
        guarded_store = store.guarded()
        self._exec(graph, entry_call, function_images, guarded_store)
        return store.load_callnode(entry_call)

    def __call__(self, graph, entry_call, function_images, store):
        return self.exec(graph, entry_call, function_images, store)

    @staticmethod
    def value_computed(callnode, store):
        return callnode in store

    @staticmethod
    def compute_and_store(callnode, func, store):
        cached_store = store.cached()
        results = func(*callnode.args, **callnode.kwargs)
        results.send(None)
        results.send(cached_store)
        while True:
            try:
                result_call, result = next(results)
                if func.can_write_to(result_call):
                    logger.debug(f'Storing result for {result_call} '
                                 f'(interface of {callnode})')
                    store.store(result_call, result)
                else:
                    msg = (f'Call {callnode} attempted to write an interface '
                           f'[{result_call.function_name}'
                           f' : hash={result_call.function_hash}] '
                           f'that is not an interface of {func.name}')
                    logger.error(msg)
                    raise XunInterfaceError(msg)
            except StopIteration as result:
                logger.debug(f'Storing result for {callnode}')
                store.store(callnode, result.value)
                return result.value
            except Exception as e:
                raise e from func.Raise()
