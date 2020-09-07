from io import StringIO
from itertools import starmap
import ast
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


def compare_ast(a, b):
    def is_relevant(node, k, v):
        ignored_keys=(
            'col_offset',
            'ctx',
            'end_col_offset',
            'end_lineno',
            'lineno',
        )

        if k.startswith('_'):
            return False

        if isinstance(node, ast.ImportFrom) and k == 'level':
            return v != 0

        return k not in ignored_keys and v is not None

    if type(a) is not type(b):
        return False

    if isinstance(a, ast.AST):
        a_attrs = {k: v for k, v in vars(a).items() if is_relevant(a, k, v)}
        b_attrs = {k: v for k, v in vars(b).items() if is_relevant(b, k, v)}

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
