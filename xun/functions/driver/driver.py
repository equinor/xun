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
    def _exec(self, graph, entry_call, function_images, store_accessor):
        pass

    def exec(self, graph, entry_call, function_images, store_accessor):
        guarded_store_accessor = store_accessor.guarded()
        self._exec(graph, entry_call, function_images, guarded_store_accessor)
        return store_accessor.client.load_result(entry_call)

    def __call__(self, graph, entry_call, function_images, store_accessor):
        return self.exec(graph, entry_call, function_images, store_accessor)

    @staticmethod
    def compute_and_store(callnode, func, store_accessor):
        results = func(*callnode.args, **callnode.kwargs)
        results.send(None)
        results.send(store_accessor)
        while True:
            try:
                result_call, result = next(results)
                if func.can_write_to(result_call):
                    logger.debug(f'Storing result for {result_call} '
                                 f'(interface of {callnode})')
                    store_accessor.store_result(result_call, result)
                else:
                    msg = (f'Call {callnode} attempted to write an interface '
                           f'[{result_call.function_name}'
                           f' : hash={result_call.function_hash}] '
                           f'that is not an interface of {func.name}')
                    logger.error(msg)
                    raise XunInterfaceError(msg)
            except StopIteration as result:
                logger.debug(f'Storing result for {callnode}')
                store_accessor.store_result(callnode, result.value)
                return result.value
            except Exception as e:
                raise e from func.Raise()
