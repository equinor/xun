from .. import CallNode
from .. import SentinelNode
from abc import ABC
from abc import abstractmethod


class Driver(ABC):
    """Driver

    Drivers are the classes that have the responsibility of executing programs.
    This includes scheduling the calls of the call graph and managing any
    concurency.
    """
    @abstractmethod
    def exec(self, graph, entry_call, function_images, store):
        pass

    def __call__(self, graph, entry_call, function_images, store):
        return self.exec(graph, entry_call, function_images, store)


def load_sentinel_value(store, sentinel):
    call = replace_sentinels(store, sentinel.call)
    return store[call]


def replace_sentinels(store, call):
    args = [
        load_sentinel_value(store, arg)
        if isinstance(arg, SentinelNode) else arg
        for arg in call.args
    ]
    kwargs = {
        key: load_sentinel_value(store, value)
        if isinstance(value, SentinelNode) else value
        for key, value in call.kwargs.items()
    }
    return CallNode(call.function_name, *args, **kwargs)
