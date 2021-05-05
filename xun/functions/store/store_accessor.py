from .. import CallNode


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

    def load_result(self, call):
        print()
        print(call)
        if not isinstance(call, CallNode):
            # raise TypeError("Not CallNode")
            print("Not a CallNode")
            return call
        namespace = self.store / 'results' / call
        print(namespace)
        res_stmt = iter(namespace[call.function_hash])
        for subscript in call.subscript:
            for _ in range(subscript):
                next(res_stmt)
            res_stmt = iter(next(res_stmt))
        res_stmt = next(res_stmt)
        print('Done loading result from store:', res_stmt)
        return res_stmt

    def store_result(self, call, result):
        namespace = self.store / 'results' / call
        namespace[call.function_hash] = result
        namespace['latest'] = call.function_hash

    def completed(self, call):
        namespace = self.store / 'results' / call
        return call.function_hash in namespace

    def resolve_call_args(self, call):
        """
        Given a call, return its arguments and keyword arguments. If any
        argument is a CallNode, the CallNode is replaced with a value loaded
        from the store.

        Parameters
        ----------
        call : CallNode

        Returns
        (list, dict)
            Pair of resolved arguments and keyword arguments
        """
        cache = {}

        def load_arg_value(arg):
            """
            If the argument is a Callnode, the result must be loaded from the
            store, unless it is already loaded in the cache.
            """
            print(f'load_arg_value({arg})')
            if isinstance(arg, CallNode):
                if len(arg.subscript) == 0:
                    return cache.setdefault(arg, self.load_result(arg))
                # In case subscript is specified, find the value at the correct
                # subscript by iterating thgough the result
                result = iter(cache.setdefault(arg, self.load_result(arg)))
                print(f'Result: {result}')
                for subscript in arg.subscript:
                    for _ in range(subscript):
                        next(result)
                    result = iter(next(result))
                return next(result)
            else:
                return arg

        args = [
            load_arg_value(arg)
            for arg in call.args
        ]
        kwargs = {
            key: load_arg_value(arg)
            for key, arg in call.kwargs.items()
        }
        print(args, kwargs)
        return args, kwargs
