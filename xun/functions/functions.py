from collections import Counter
from collections import namedtuple
from itertools import chain
from typing import Any
from typing import Dict
from typing import List
import ast
import copy
import inspect
import textwrap
import types


class CopyError(Exception): pass
class FunctionDefNotFoundError(Exception): pass
class FunctionError(Exception): pass
class NotDAGError(Exception): pass


class Function:
    def __init__(self, func_or_desc, attrs=None, deleted=frozenset()):
        self.keys = ()
        if attrs is not None:
            for name, value in attrs.items():
                self.keys += (name,)
                super().__setattr__(name, value)
        self.desc = (
            func_or_desc
            if isinstance(func_or_desc, FunctionDescription)
            else describe(func_or_desc)
        )
        self.deleted = deleted

        self.ast = copy.deepcopy(self.desc.ast.body)

        self.lock = True

    def __setattr__(self, name, value):
        if hasattr(self, 'lock'):
            raise AttributeError('can\'t set attribute')
        super().__setattr__(name, value)

    def __getattr__(self, name):
        if name in super().__getattribute__('deleted'):
            raise AttributeError('{} is deleted'.format(name))
        return super().__getattribute__(name)

    def apply(self, transformation, *args, **kwargs):
        return transformation(self, *args, **kwargs)

    def compile(self, *nodes):
        args = self.desc.ast.args

        body = list(chain(*nodes))

        fdef = ast.fix_missing_locations(ast.Module(
            type_ignores=[],
            body=[
                ast.FunctionDef(
                    name=self.desc.name,
                    args=args,
                    decorator_list=[],
                    body=body,
                )
            ],
        ))

        function_code = compile(fdef, '<string>', 'exec')

        namespace = {}
        exec(function_code, namespace)
        f = namespace[self.desc.name]

        return overwrite_globals(f, self.desc.globals, self.desc.module)

    def update(self, deleted: List[str], new: Dict[str, Any]):
        for key in new.keys():
            if key in self.keys:
                raise AttributeError('Key {} already exists'.format(key))
        attrs = {
            **{ k: getattr(self, k)
                for k in self.keys
                if not k in deleted },
            **{ k: v
                for k, v in new.items()
                if not k in deleted },
        }
        new_deleted = self.deleted | frozenset(deleted)

        f = Function(self.desc, attrs=attrs, deleted=new_deleted)

        return f


def function_ast(func):
    source = inspect.getsource(func)
    dedent = textwrap.dedent(source)
    return ast.parse(dedent)


def overwrite_globals(func, globals, module=None):
    """
    Returns a new function, with the same code as the given, but with the given
    scope
    """
    g = types.FunctionType(
        func.__code__,
        globals,
        name=func.__name__,
        argdefs=func.__defaults__,
        closure=func.__closure__,
    )
    if module is not None:
        g.__module__ = module
    g.__kwdefaults__ = copy.copy(func.__kwdefaults__)
    return g


def describe(func):
    tree = function_ast(func)

    is_single_function_module = (isinstance(tree, ast.Module)
        and len(tree.body) == 1
        and isinstance(tree.body[0], ast.FunctionDef)
    )

    if not is_single_function_module:
        raise ValueError('can only describe a single function')

    func_tree = tree.body[0]

    describer = Describer()
    describer.visit(func_tree)

    return FunctionDescription(
        ast=func_tree,
        name=describer.func_name,
        args=describer.func_args,
        varargs=describer.func_varargs,
        kwonlyargs=describer.func_kwonlyargs,
        globals=func.__globals__,
        module=func.__module__,
    )


FunctionDescription = namedtuple(
    'FunctionDescription',
    [
        'ast',
        'name',
        'args',
        'varargs',
        'kwonlyargs',
        'globals',
        'module',
    ]
)


class Describer(ast.NodeVisitor):
    def __init__(self):
        self.func_node = None
        self.func_name = None
        self.func_args = None
        self.func_varargs = None
        self.func_kwonlyargs = None

    def visit(self, node):
        r = super().visit(node)

        if self.func_node is None:
            raise FunctionDefNotFoundError('Could not find function definition')

        return r

    def visit_FunctionDef(self, node):
        if self.func_node is not None:
            raise FunctionError('More than one function definition')
        self.func_node = node
        self.func_name = node.name
        self.func_args = [a.arg for a in node.args.args]
        self.func_varargs = []
        self.func_kwonlyargs = []
