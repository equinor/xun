from abc import abstractmethod
from collections.abc import KeysView
from collections.abc import MutableMapping
import copy


class Store(MutableMapping):
    """Store

    In xun stores are used to keep track of executed calls, and their results.
    They implement mutable mappings and are namespaced. Namespaces can be
    accessed using the true division operator. The floor division operator can
    be used to access store values, similar to __getitem__.

    Values in namespaces are visible only to that particular namespace, meaning
    that child namespace and their values are not visible to the parent
    namespace itself.

    Recreating a store, by pickle/unpickle or copy, will result in a store
    object accessing the _same_ underlying store. That is, changes done to an
    instance are reflected in any other instances or recreations of this
    particular store.

    Examples
    --------

    >>> some_namespace = store / 'some_namespace'
    >>> namespace_1 = store / 1
    >>> some_namespace['key'] = 'Value'
    >>> 'key' in some_namespace
    True
    >>> 'key' in namespace_1
    False
    >>> store / 'some_namespace' // 'key'
    'Value'

    """
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._namespace = ()
        return instance

    @property
    @abstractmethod
    def driver(self):
        pass

    @property
    def namespace(self):
        return self._namespace

    def __getstate__(self):
        return self._namespace

    def __setstate__(self, state):
        self._namespace = state

    def __floordiv__(self, other):
        return self[other]

    def __truediv__(self, other):
        new_instance = copy.copy(self)
        new_instance._namespace = (*self.namespace, other)
        return new_instance

    def __contains__(self, key):
        key = NamespacedKey(self.namespace, key)
        return self.driver.__contains__(key)

    def __delitem__(self, key):
        key = NamespacedKey(self.namespace, key)
        self.driver.__delitem__(key)

    def __eq__(self, other):
        if type(self) is not type(other):
            return False
        return (
            self.namespace == other.namespace and
            self.driver == other.driver
        )

    def __getitem__(self, key):
        key = NamespacedKey(self.namespace, key)
        return self.driver.__getitem__(key)

    def __iter__(self):
        return iter(self.driver.namespace_keys(self.namespace))

    def __len__(self):
        return self.driver.namespace__len__(self.namespace)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __setitem__(self, key, value):
        key = NamespacedKey(self.namespace, key)
        self.driver.__setitem__(key, value)

    def clear(self):
        self.driver.namespace_clear(self.namespace)

    def __repr__(self):
        r = repr(self.driver)
        if len(self.namespace) > 0:
            r = '({} / {})'.format(
                r,
                ' / '.join(repr(n) for n in self.namespace)
            )
        return r


class StoreDriver(MutableMapping):
    def namespace__len__(self, namespace):
        return sum(1 for _ in self.namespace_keys(namespace))

    def namespace_clear(self, namespace):
        removed = [k for k in self if k.namespace == namespace]
        for key in removed:
            del self[key]

    def namespace_keys(self, namespace):
        filtered = filter(lambda k: k.namespace == namespace, self)
        return KeysView(k.key for k in filtered)


class NamespacedKey:
    def __init__(self, namespace, key):
        if isinstance(key, NamespacedKey):
            namespace += key.namespace
            key = key.key
        self.namespace = namespace
        self.key = key

    def __getstate__(self):
        return self.namespace, self.key

    def __setstate__(self, state):
        self.namespace = state[0]
        self.key = state[1]

    def __eq__(self, other):
        return self.namespace == other.namespace and self.key == other.key

    def __hash__(self):
        return hash((self.namespace, self.key))

    def __repr__(self):
        fmt = 'NamespacedKey(namespace={}, key={})'
        return fmt.format(repr(self.namespace), repr(self.key))
