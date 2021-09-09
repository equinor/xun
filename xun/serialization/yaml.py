from . import numpy_types
from . import pandas_types
from . import python_types
from . import xun_types
from io import StringIO
import datetime
import hashlib
import yaml


_xun_functors = (
    numpy_types.NumpyFunctor,

    pandas_types.FrameFunctor,
    pandas_types.SeriesFunctor,

    python_types.FrozenmapFunctor,
    python_types.FrozensetFunctor,
    python_types.PathFunctor,
    python_types.SetFunctor,
    python_types.TupleFunctor,

    xun_types.CallNodeFunctor,
    xun_types.NamespacedKeyFunctor,
)
mapping_type = (dict, )
sequence_types = (tuple, list)
scalar_types = (
    type(None),
    str,
    bool,
    int,
    float,
    datetime.date,
    datetime.datetime,
)


def representer(functor):
    def _representer(dumper, value):

        _tag = tag(functor)

        reduced = functor(value)
        yaml_type = type(reduced)

        if yaml_type in mapping_type:
            return dumper.represent_mapping(_tag,
                                            reduced,
                                            flow_style=False)
        elif yaml_type in sequence_types:
            return dumper.represent_sequence(_tag,
                                             reduced,
                                             flow_style=False)
        elif yaml_type in scalar_types:
            return dumper.represent_scalar(_tag, reduced)

        raise ValueError(f'Native yaml type expected, got {yaml_type}')

    return _representer


def constructor(functor):
    inverse = ~functor

    def _constructor(*yaml_args):
        # Two args for add_constructor, three for add_multi_constructor
        # https://github.com/eevee/camel/blob/1f9132ce43f6933bd3e91681404aab817876b3e1/camel/__init__.py#L305
        if len(yaml_args) == 3:
            loader, suffix, node = yaml_args
        else:
            loader, node = yaml_args

        if isinstance(node, yaml.ScalarNode):
            data = loader.construct_scalar(node)
        elif isinstance(node, yaml.SequenceNode):
            data = loader.construct_sequence(node, deep=True)
        elif isinstance(node, yaml.MappingNode):
            data = loader.construct_mapping(node, deep=True)
        else:
            raise TypeError("Not a primitive node: {!r}".format(node))

        return inverse(data)

    return _constructor


def tag(functor):
    return f'!xun/{functor.__qualname__}::{functor.hash.hex()}'


class XunDumper(yaml.SafeDumper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.yaml_representers = yaml.SafeDumper.yaml_representers.copy()
        self.yaml_multi_representers = (
            yaml.SafeDumper.yaml_multi_representers.copy()
        )
        for functor in _xun_functors:
            types, mro_types = functor._internal_type
            F = representer(functor)
            self.yaml_representers.update({t: F for t in types})
            self.yaml_multi_representers.update({t: F for t in mro_types})

    def generate_anchor(self, node):
        shake_128 = hashlib.shake_128()
        shake_128.update(repr(node).encode())
        return shake_128.hexdigest(16)

    def add_representer(self, data_type, representer):
        if data_type in self.yaml_representers:
            raise ValueError(f'Multiple reducers for {data_type}')
        self.yaml_representers[data_type] = representer

    def add_multi_representer(self, data_type, representer):
        if data_type in self.yaml_multi_representers:
            raise ValueError(f'Multiple reducers for {data_type}')
        self.yaml_multi_representers[data_type] = representer


class XunLoader(yaml.SafeLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.yaml_constructors = yaml.SafeLoader.yaml_constructors.copy()
        self.yaml_multi_constructors = (
            yaml.SafeLoader.yaml_multi_constructors.copy()
        )
        self.yaml_implicit_resolvers = (
            yaml.SafeLoader.yaml_implicit_resolvers.copy()
        )
        for functor in _xun_functors:
            self.yaml_constructors[tag(functor)] = constructor(functor)

    def add_constructor(self, data_type, constructor):
        self.yaml_constructors[data_type] = constructor

    def add_multi_constructor(self, data_type, constructor):
        self.yaml_multi_constructors[data_type] = constructor


def dump(obj, stream, functor=None):
    dumper = XunDumper(stream, default_flow_style=False)

    if functor is not None:
        dumper.add_representer(functor, representer(functor))
        obj = functor.unit(obj)

    dumper.open()
    dumper.represent(obj)
    dumper.close()


def dumps(obj, functor=None):
    stream = StringIO()
    dump(obj, stream, functor)
    return stream.getvalue()


def load(stream, functor=None):
    loader = XunLoader(stream)

    if functor is not None:
        loader.add_constructor(tag(functor), constructor(functor))

    return loader.get_data()


def loads(data, functor=None):
    stream = StringIO(data)
    return load(stream, functor)
