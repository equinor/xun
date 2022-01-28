from io import StringIO
from math import radians
from math import sin
from xun.functions.compatibility import ast
import astor
import astunparse
import difflib
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
    def exec(self,
             graph,
             entry_call,
             function_images,
             store,
             global_resources):
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
            global_resources=global_resources,
        )


class PicklableMemoryStore(xun.functions.store.Memory):
    """ PicklableMemoryStore
    Works under the assumption that the object is never replicated outside of
    the creating process.
    """

    _cached_stores = {}

    def __init__(self):
        super().__init__()
        self.id = id(self)

    def __getstate__(self):
        return self.id

    def __setstate__(self, state):
        self.id = state
        self._container = PicklableMemoryStore._cached_stores[self.id]._container

    def __enter__(self):
        PicklableMemoryStore._cached_stores.setdefault(self.id, self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del PicklableMemoryStore._cached_stores[self.id]
        return exc_type is None


def run_in_process(blueprint, **kwargs):
    return blueprint.run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
        **kwargs,
    )


def sample_sin_blueprint(offset=42, sample_count=10, step_size=36):
    @xun.function()
    def mksample(i, step_size):
        return i * step_size

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
        sin(radians(i * step_size)) + offset for i in range(sample_count)
    ]

    return blueprint, expected


def check_ast_equals(a, b):
    if isinstance(a, list):
        assert isinstance(b, list)
        a = ast.Module(body=a)
        b = ast.Module(body=b)
    if not ast.dump(a) == ast.dump(b):
        differ = difflib.Differ()
        a_ast = astunparse.dump(a).splitlines(keepends=True)
        b_ast = astunparse.dump(b).splitlines(keepends=True)
        a_src = astor.to_source(a).splitlines(keepends=True)
        b_src = astor.to_source(b).splitlines(keepends=True)
        diff = ''.join(differ.compare(a_src, b_src)
            ) if a_src != b_src else ''.join(differ.compare(a_ast, b_ast))
        return False, diff
    return True, ''
