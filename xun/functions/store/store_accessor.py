from .. import CallNode
from .. import CallNodeSubscript


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
    load_result(call, hash=None)
        Loads a result for a call, use hash to specify a specific function
        version
    store_result(call, hash, result)
        Stores a result for a call and function hash. The latest reference is
        updated to point to this result
    completed(call, hash=None)
        True if there is a value stored for a given call. If hash is not
        supplied, we check against the latest stored result.
    """

    def __init__(self, store):
        self.store = store

    @property
    def client(self):
        if self.store.client_store is not None:
            return StoreAccessor(self.store.client_store)
        else:
            return self

    def load_result(self, call, hash=None):
        namespace = self.store / 'results' / call
        hash = hash if hash is not None else namespace['latest']
        return namespace[hash]

    def store_result(self, call, hash, result):
        namespace = self.store / 'results' / call
        namespace[hash] = result
        namespace['latest'] = hash

    def completed(self, call, hash=None):
        namespace = self.store / 'results' / call

        if hash is not None:
            return hash in namespace

        if 'latest' in namespace:
            hash = namespace['latest']
            return hash in namespace

        return False

    def resolve_call_args(self, call):
        """
        Given a call, return its arguments and keyword arguments. If any
        argument is a CallNode or a CallNodeSubscript, the CallNode or
        CallNodeSubscript is replaced with a value loaded from the store.

        Parameters
        ----------
        call : CallNode or CallNodeSubscript

        Returns
        (list, dict)
            Pair of resolved arguments and keyword arguments
        """
        cache = {}

        def load_arg_value(arg):
            """
            The argument can be either a CallNode or a CallNodeSubscript. If
            so, the result must be loaded from store, unless it is already
            loaded in the cache.
            """
            if isinstance(arg, CallNode):
                return cache.setdefault(arg, self.load_result(arg))
            elif isinstance(arg, CallNodeSubscript):
                # Load the result from the parent CallNode
                call = arg.call
                result = iter(cache.setdefault(call, self.load_result(call)))
                # Find the value at the correct subscript by iterating through
                # the result
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
        return args, kwargs
