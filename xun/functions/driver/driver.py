from abc import ABC
from abc import abstractmethod


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
        self._exec(graph, entry_call, function_images, store_accessor)
        return store_accessor.client.load_result(entry_call)

    def __call__(self, graph, entry_call, function_images, store_accessor):
        return self.exec(graph, entry_call, function_images, store_accessor)
