from io import StringIO
from itertools import starmap
from math import radians
from math import sin
from xun.functions.compatibility import ast
import fakeredis
import sys
import xun


class capture_stdout(StringIO):
    def __init__(self):
        super(capture_stdout, self).__init__()

    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self
        return self

    def __exit__(self, *args):
        sys.stdout = self._stdout
        self.seek(0)


class PickleDriver(xun.functions.driver.Sequential):
    """
    Test driver ensuring that anything touched by the driver can be pickled
    """
    def exec(self, graph, entry_call, function_images, store):
        import pickle

        P = {
            'graph': pickle.dumps(graph),
            'entry_call': pickle.dumps(entry_call),
            'function_images': pickle.dumps(function_images),
            'store': pickle.dumps(store),
        }

        return super().exec(
            graph=pickle.loads(P['graph']),
            entry_call=pickle.loads(P['entry_call']),
            function_images=pickle.loads(P['function_images']),
            store=pickle.loads(P['store']),
        )


class PicklableMemoryStore(xun.functions.store.Store):
    """ PicklableMemoryStore
    Works under the assumption that the object is never replicated outside of
    the creating process.
    """

    class Driver(dict, xun.functions.store.StoreDriver):
        pass

    _drivers = {}

    def __init__(self):
        self.id = id(self)

    @property
    def driver(self):
        if self.id not in PicklableMemoryStore._drivers:
            raise ValueError('No context for this store')
        return PicklableMemoryStore._drivers[self.id]

    def __getstate__(self):
        return self.id

    def __setstate__(self, state):
        self.id = state

    def __enter__(self):
        PicklableMemoryStore._drivers.setdefault(
            self.id,
            PicklableMemoryStore.Driver(),
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del PicklableMemoryStore._drivers[self.id]
        return exc_type is None


class FakeRedis(xun.functions.store.Redis):
    _servers = {}

    class Driver(xun.functions.store.redis.RedisDriver):
        def __init__(self, server):
            self.redis = fakeredis.FakeStrictRedis(server=server)

    def __init__(self):
        super().__init__()

        # The ID is used to identify the server that this instance and any
        # copies of it should connect to
        self._id = id(self)

    @property
    def driver(self):
        try:
            return self._driver
        except AttributeError:
            server = FakeRedis._servers[self._id]
            self._driver = FakeRedis.Driver(server)
            return self._driver

    def __getstate__(self):
        return super().__getstate__(), self._id

    def __setstate__(self, state):
        super().__setstate__(state[0])
        self._id = state[1]

    def __enter__(self):
        FakeRedis._servers.setdefault(self._id, fakeredis.FakeServer())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del FakeRedis._servers[self._id]
        return exc_type is None


def compare_ast(a, b):
    def is_relevant(node, k):
        ignored_keys = (
            'col_offset',
            'end_col_offset',
            'end_lineno',
            'lineno',
        )
        return k not in ignored_keys

    if type(a) is not type(b):
        return False

    if isinstance(a, ast.AST):
        a_attrs = {k: v for k, v in vars(a).items() if is_relevant(a, k)}
        b_attrs = {k: v for k, v in vars(b).items() if is_relevant(b, k)}

        if set(a_attrs.keys()) != set(b_attrs.keys()):
            return False

        for key in a_attrs.keys():
            if not compare_ast(a_attrs[key], b_attrs[key]):
                return False
        return True
    elif isinstance(a, list):
        return all(starmap(compare_ast, zip(a, b)))
    else:
        return a == b


def sample_sin_blueprint(offset=42, sample_count=10, step_size=36):
    @xun.function()
    def mksample(i, step_size):
        return i / step_size

    @xun.function()
    def deg_to_rad(deg):
        return radians(deg)

    @xun.function()
    def sample_sin(offset, sample_count, step_size):
        return [sin(s) + offset for s in radians]
        with ...:
            samples = [mksample(i, step_size) for i in range(sample_count)]
            radians = [deg_to_rad(s) for s in samples]

    blueprint = sample_sin.blueprint(offset, sample_count, step_size)
    expected = [
        sin(radians(i / step_size)) + offset for i in range(sample_count)
    ]

    return blueprint, expected
