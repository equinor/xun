class Reference:
    def __init__(self, data):
        self._referencing = data

    @classmethod
    def to_callnode(cls, callnode):
        inst = cls.__new__(cls)
        inst.callnode = callnode
        return inst

    @property
    def value(self):
        return self.store.load_callnode(self.callnode)
