class StoreAccessor:
    """ StoreAccessor

    Convenience class used by drivers and generated code to structure the
    store. Function hashes are used to identify versions of functions. The hash
    of the function is used to identify a result for a specific function
    version.

    `store / 'results' / call // hash`

    For each CallNode namespace in the store, a key 'latest' stores the hash of
    the latest version of the CallNodes function.

    Methods
    -------
    load_result(call)
        Loads a result for a call
    store_result(call, result)
        Stores a result for a call. The latest reference is updated to point to
        this result
    completed(call)
        True if there is a value stored for a given call.
    """

    def __init__(self, store, client_store=None):
        self.store = store
        self.client_store = client_store

    @property
    def client(self):
        if self.client_store is not None:
            return StoreAccessor(self.client_store)
        else:
            return self

    def guarded(self):
        inst = GuardedStoreAccessor.__new__(GuardedStoreAccessor)
        inst.__dict__.update(vars(self))
        inst._written = set()
        return inst

    def load_result(self, call):
        namespace = self.store / call.function_hash
        result = namespace[(call.args, call.kwargs)]
        for subscript in call.subscript:
            result = result[subscript]
        return result

    def store_result(self, call, result):
        namespace = self.store / call.function_hash
        namespace[(call.args, call.kwargs)] = result

    def completed(self, call):
        namespace = self.store / call.function_hash
        return (call.args, call.kwargs) in namespace


class GuardedStoreAccessor(StoreAccessor):
    class StoreError(Exception):
        pass

    def store_result(self, call, result):
        if call in self._written:
            raise self.StoreError(f'Multiple results for {call}')
        self._written.add(call)
        super().store_result(call, result)
