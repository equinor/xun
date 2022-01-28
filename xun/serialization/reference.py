class Reference:
    def __init__(self, data):
        self._referencing = data

    @classmethod
    def to_callnode(cls, node):
        inst = cls.__new__(cls)
        inst.callnode = node
        return inst

    @property
    def value(self):
        return self.store.load_callnode(self.callnode)
