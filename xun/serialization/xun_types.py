from ..functions import CallNode
from .functor import IsoFunctor
from .functor import _internal_type


@_internal_type(CallNode)
class CallNodeFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, value):
            return CallNode(
                value['function_name'],
                value['function_hash'],
                *value['args'],
                **value['kwargs'],
            )._replace(subscript=value['subscript'])

        def __invert__(cls):
            return CallNodeFunctor

    def __call__(cls, value):
        return {
            'function_name': value.function_name,
            'function_hash': value.function_hash,
            'subscript': value.subscript,
            'args': value.args,
            'kwargs': value.kwargs,
        }

    def __invert__(cls):
        return cls._Inverse
