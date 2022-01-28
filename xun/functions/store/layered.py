from .store import Store


class Layered(Store):
    """ Layered Store

    Store with one or more fallback stores. New writes are stored in the top
    layer, that is, the store that was the first argument to the function.

    Examples
    --------

    >>> @xun.function()
    ... def f(a):
    ...     return a * 2
    ...
    >>> mem = xun.functions.store.Memory()
    >>> disk = xun.functions.store.Disk('~/xun-store')
    >>> disk.store(f.callnode(2), 4)
    >>> layered = xun.functions.store.Layered(mem, disk)
    >>> layered.store(f.callnode(3), 6)
    >>> f.callnode(2) in mem
    False
    >>> f.callnode(2) in disk
    True
    >>> f.callnode(2) in layered
    True
    >>> f.callnode(3) in mem
    True
    >>> f.callnode(3) in disk
    False
    >>> f.callnode(3) in layered
    True
    """

    def __init__(self, *layers):
        if len(layers) == 0:
            raise ValueError('No store layers supplied')
        self._layers = layers

    def __contains__(self, callnode):
        return any(callnode in layer for layer in self._layers)

    def _load_value(self, callnode):
        for layer in self._layers:
            if callnode in layer:
                return layer[callnode]
        raise KeyError(repr(callnode))

    def _store(self, callnode, value, **tags):
        self._layers[0].store(callnode, value, **tags)

    def remove(self, callnode):
        del self._layers[0][callnode]

    def _load_tags(self, callnode):
        raise NotImplementedError

    def filter(self, *tag_conditions):
        raise NotImplementedError

    def __getstate__(self):
        return self._layers

    def __setstate__(self, state):
        self._layers = state
