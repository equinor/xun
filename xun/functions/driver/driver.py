from .. import CallNode
from .. import FutureValueNode
from abc import ABC
from abc import abstractmethod


class Driver(ABC):
    """Driver

    Drivers are the classes that have the responsibility of executing programs.
    This includes scheduling the calls of the call graph and managing any
    concurrency.
    """
    @abstractmethod
    def exec(self, graph, entry_call, function_images, store):
        pass

    def __call__(self, graph, entry_call, function_images, store):
        return self.exec(graph, entry_call, function_images, store)


def replace_futures(store, call):
    """
    Given a call, replace any FutureValueNodes with values from the store.

    Parameters
    ----------
    store : Store
        Store to load from
    call : CallNode

    Returns
    CallNode
        Call with FutureValueNodes replaced by the value they represent
    """
    args = [
        store[arg]
        if isinstance(arg, FutureValueNode) else arg
        for arg in call.args
    ]
    kwargs = {
        key: store[value]
        if isinstance(value, FutureValueNode) else value
        for key, value in call.kwargs.items()
    }
    return CallNode(call.function_name, *args, **kwargs)
