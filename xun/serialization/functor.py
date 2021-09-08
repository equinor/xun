from ..functions import describe
import hashlib
import inspect


def _internal_type(*types, mro_types=()):
    """
    This decorator is just used to internalness of functors with special
    behavior. It should not be used in client code.
    """
    def decorator(cls):
        cls._internal_type = types, mro_types
        return cls
    return decorator


def hash_methods(functor_name, *methods):
    sha256 = hashlib.sha256()
    sha256.update(functor_name.encode())
    for method in methods:
        desc = describe(method)
        sha256.update(desc.src.encode())
    return sha256.digest()


class IsoFunctor(type):
    def __new__(cls, name, bases, attrs):
        if '__call__' not in attrs:
            raise TypeError('IsoFunctor types must implement __call__')
        if '__invert__' not in attrs:
            raise TypeError('IsoFunctor types must implement __invert__')

        hash = hash_methods(name, attrs['__call__'], attrs['__invert__'])

        for k, v in attrs.items():
            if inspect.isfunction(v):
                attrs[k] = classmethod(v)

        attrs['_one_way_hash'] = hash

        return type.__new__(cls, name, bases, attrs)

    def __call__(cls, value):
        if type(value) is cls:
            value = value._value
        return cls.__call__(value)

    def __invert__(cls):
        return cls.__invert__()

    @property
    def hash(cls):
        cls_hash = cls._one_way_hash
        inv_hash = (~cls)._one_way_hash

        sha256 = hashlib.sha256()
        for h in sorted([cls_hash, inv_hash]):
            sha256.update(h)

        return sha256.digest()

    def unit(cls, wrapped):
        inst = cls.__new__(cls)
        inst._value = wrapped
        return inst
