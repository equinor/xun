from .functor import IsoFunctor
from .functor import _internal_type
from immutables import Map as frozenmap
import pathlib


@_internal_type(tuple)
class TupleFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, value):
            return tuple(value)

        def __invert__(cls):
            return TupleFunctor

    def __call__(cls, value):
        return value

    def __invert__(cls):
        return cls._Inverse


@_internal_type(set)
class SetFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, value):
            return set(value)

        def __invert__(cls):
            return SetFunctor

    def __call__(cls, value):
        return cls.coerce_set(value)

    def __invert__(cls):
        return cls._Inverse

    def coerce_set(cls, S):
        """ In order to support sets of mixed type, we sort on type first. """
        types = set(type(v) for v in S)
        type_repr = set(repr(t) for t in types)
        if len(types) != len(type_repr):
            raise TypeError(f'Could not coerce set to sorted list {S}')
        return sorted(S, key=lambda v: (repr(type(v)), v))


@_internal_type(frozenset)
class FrozensetFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, value):
            return frozenset(value)

        def __invert__(cls):
            return FrozensetFunctor

    def __call__(cls, value):
        return SetFunctor.coerce_set(value)

    def __invert__(cls):
        return cls._Inverse


@_internal_type(frozenmap)
class FrozenmapFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, value):
            return frozenmap(value)

        def __invert__(cls):
            return FrozenmapFunctor

    def __call__(cls, value):
        return dict(value)

    def __invert__(cls):
        return cls._Inverse


@_internal_type(mro_types=(pathlib.Path, ))
class PathFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, value):
            return pathlib.Path(value)

        def __invert__(cls):
            return PathFunctor

    def __call__(cls, value):
        return str(value)

    def __invert__(cls):
        return cls._Inverse
