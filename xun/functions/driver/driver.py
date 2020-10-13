from ..store import StoreAccessor
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

    def exec(self, graph, entry_call, function_images, store):
        store_accessor = StoreAccessor(store)
        store_accessor.store_graph(
            graph,
            lambda node: function_images[node.function_name].hash
        )
        return self._exec(graph, entry_call, function_images, store_accessor)

    def __call__(self, graph, entry_call, function_images, store):
        return self.exec(graph, entry_call, function_images, store)
