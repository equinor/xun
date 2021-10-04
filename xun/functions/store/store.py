from abc import ABC, abstractmethod


class Store(ABC):
    @abstractmethod
    def __contains__(self, key):
        pass

    def __getitem__(self, key):
        return self.load(key)

    @abstractmethod
    def load(self, key):
        pass

    @abstractmethod
    def tags(self, key):
        pass

    @abstractmethod
    def store(self, key, value, **tags):
        pass

    def guarded(self):
        return GuardedStoreAccessor(self)


class GuardedStoreAccessor(Store):
    def __init__(self, store):
        self._wrapped_store = store
        self._written = set()

    def __contains__(self, key):
        return key in self._wrapped_store

    def load(self, key):
        return self._wrapped_store.load(key)

    def metadata(self, key):
        return self._wrapped_store.metadata(key)

    def store(self, key, value, **metadata):
        if call in self._written:
            raise self.StoreError(f'Multiple results for {call}')
        self._written.add(key)
        return self._wrapped_store.store(key, value, **metadata)

    def guarded(self):
        return self
