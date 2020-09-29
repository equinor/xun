from .. import CallNode
import hashlib
import secrets


class StoreAccessor:
    def __init__(self, store):
        self.store = store

    def load_result(self, call, func=None):
        namespace = self.store / 'results' / call
        hash = func.hash if func is not None else namespace['latest']
        return namespace[hash]

    def store_result(self, call, func, result):
        namespace = self.store / 'results' / call
        namespace[func.hash] = result
        namespace['latest'] = func.hash

    def completed(self, call, func=None):
        namespace = self.store / 'results' / call
        hash = func.hash if func is not None else namespace['latest']
        return hash in namespace

    def invalidate(self, call, func=None):
        if not self.completed(call):
            return

        namespace = self.store / 'results' / call

        hash = func.hash if func is not None else namespace['latest']

        sha256 = hashlib.sha256(bytes.fromhex(hash))
        sha256.update(secrets.token_bytes(32))
        distorted = sha256.hexdigest()

        namespace[distorted] = namespace.pop(hash)
        if namespace['latest'] == hash:
            namespace['latest'] = distorted

    def resolve_call(self, call):
        """
        Given a call, replace any FutureValueNodes with values from the store.

        Parameters
        ----------
        call : CallNode

        Returns
        CallNode
            Call with FutureValueNodes replaced by the value they represent
        """
        args = [
            self.load_result(arg)
            if isinstance(arg, CallNode) else arg
            for arg in call.args
        ]
        kwargs = {
            key: self.load_result(value)
            if isinstance(value, CallNode) else value
            for key, value in call.kwargs.items()
        }
        return CallNode(call.function_name, *args, **kwargs)
