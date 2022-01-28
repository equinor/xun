class Reference:
    _guard = object()

    def __init__(self, data):
        self._referencing = data

    @property
    def is_new(self):
        return self._referencing is not self._guard

    @classmethod
    def to_callnode(cls, callnode):
        inst = cls.__new__(cls)
        inst.callnode = callnode
        inst._referencing = cls._guard
        return inst

    @property
    def value(self):
        return self.store.load_callnode(self.callnode)
