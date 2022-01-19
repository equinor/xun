from ... import serialization
from ...fs.queries import parse
from abc import ABC, abstractmethod
from uuid import uuid4
import base64
import contextlib
import hashlib
import sqlite3
import struct


def restructure(data, shape):
    def shape_iter(shape, depth=0):
        if shape == ...:
            return [(), ]
        return [
            (expr.tag, *tail)
            for expr, child in shape.items()
            for tail in shape_iter(child, depth + 1)
        ]
    paths = shape_iter(shape)

    result = {} if shape != ... else set()
    for callnode, tags in data.items():
        for path in paths:
            values = [tags[p] for p in path]
            bucket = result
            if len(values) > 0:
                for value in values[:-1]:
                    bucket = bucket.setdefault(value, {})
                bucket = bucket.setdefault(values[-1], set())
            bucket.add(callnode)
    return result


def selection_from_query_syntax(query):
    def hierarchy_to_shape(hierarchies):
        if hierarchies == ...:
            return ...
        return {
            _Tag(hierarchy.expr): hierarchy_to_shape(hierarchy.children)
            for hierarchy in hierarchies
        }

    def arguments_to_conditions(arguments):
        return [_Tag(tag, op, value) for tag, op, value in arguments.args]

    args = arguments_to_conditions(query.arguments)
    tree = hierarchy_to_shape(query.hierarchy)
    return args, tree


class Store(ABC):
    @abstractmethod
    def __contains__(self, key):
        pass

    def __getitem__(self, key):
        return self.load_callnode(key)

    @property
    def tags(self):
        return _Tags(self)

    @abstractmethod
    def _load_value(self, key):
        pass

    @abstractmethod
    def _load_tags(self, key):
        pass

    @abstractmethod
    def filter(self, *conditions):
        pass

    @abstractmethod
    def store(self, key, value, **tags):
        pass

    @abstractmethod
    def remove(self, key):
        pass

    def load_callnode(self, callnode):
        result = self._load_value(callnode._replace(subscript=()))
        for subscript in callnode.subscript:
            result = result[subscript]
        return result

    def select(self, *tag_conditions, shape=...):
        selected = self.filter(*tag_conditions)
        with_tags = {callnode: self.tags[callnode] for callnode in selected}
        return restructure(with_tags, shape)

    def query(self, query_string):
        conditions, shape = selection_from_query_syntax(parse(query_string))
        return self.select(*conditions, shape=shape)

    def guarded(self):
        return GuardedStore(self)

    def cached(self):
        return CachedStore(self)


class GuardedStore(Store):
    class StoreError(Exception):
        pass

    def __init__(self, store):
        self._wrapped_store = store
        self._written = set()

    def __contains__(self, key):
        return key in self._wrapped_store

    def _load_value(self, key):
        return self._wrapped_store._load_value(key)

    def _load_tags(self, key):
        return self._wrapped_store._load_tags(key)

    def filter(self, *conditions):
        return self._wrapped_store.filter(*conditions)

    def store(self, key, value, **tags):
        if key in self._written:
            raise self.StoreError(f'Multiple results for {key}')
        self._written.add(key)
        return self._wrapped_store.store(key, value, **tags)

    def remove(self, key):
        self._wrapped_store.remove(key)

    def guarded(self):
        return self


class CachedStore(Store):
    def __init__(self, store):
        self._wrapped_store = store
        self._cache = {}

    def __contains__(self, key):
        return key in self._wrapped_store

    def _load_value(self, key):
        try:
            return self._cache[key]
        except KeyError:
            value = self._wrapped_store._load_value(key)
            self._cache[key] = value
            return self._cache[key]

    def _load_tags(self, key):
        return self._wrapped_store._load_tags(key)

    def filter(self, *conditions):
        return self._wrapped_store.filter(*conditions)

    def store(self, key, value, **tags):
        return self._wrapped_store.store(key, value, **tags)

    def remove(self, key):
        self._wrapped_store.remove(key)

    def cached(self):
        return self


class _Tags:
    def __init__(self, store):
        self.store = store

    def __getitem__(self, key):
        return self.store._load_tags(key)

    def __getattr__(self, name):
        return _Tag(name)


class _Tag:
    def __init__(self, tag, op=None, value=None):
        if op is not None or value is not None:
            if op is None:
                raise ValueError('op must be specified if value is provided')
            if value is None:
                raise ValueError('value must be specified if op is not None')
        self.tag = tag
        self.op = op
        self.value = value

    def __call__(self, value):
        if self.op is None:
            return True
        return self.op(value, self.value)

    def __eq__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '='
        self.value = other
        return self

    def __ne__(self, other):
        raise ValueError('Cannot negate tag equality')

    def __lt__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '<'
        self.value = other
        return self

    def __le__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '<='
        self.value = other
        return self

    def __gt__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '>'
        self.value = other
        return self

    def __ge__(self, other):
        if not isinstance(other, str):
            raise TypeError('expected string value')
        self.op = '>='
        self.value = other
        return self

    def __hash__(self):
        return hash((self.tag, self.op, self.value))

    def __repr__(self):
        r = f'[{self.tag}]'
        if self.op is not None:
            r += f' {self.op} {self.value}'
        return f'<tag {r}>'

    def __str__(self):
        if self.op is not None:
            return f'{self.tag}{self.op}{self.value}'
        else:
            return self.tag
