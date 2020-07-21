from .functions import describe
from .functions import FunctionInfo
from .functions import overwrite_globals
from itertools import chain
from typing import Any
from typing import Dict
from typing import List
import ast
import copy
import pickle


class Function:
    def __init__(self,
                 tree,
                 name,
                 defaults,
                 globals,
                 module_infos,
                 module,
                 callable=True):
        self.tree = tree
        self.name = name
        self.defaults = defaults
        self.globals = globals
        self.module_infos = module_infos
        self.module = module
        self.callable = callable
        self._func = None

        if self.globals is None:
            raise Exception(str(self.__dict__))

    @staticmethod
    def from_function(func, callable=True):
        desc = describe(func)
        return Function.from_description(desc, callable=callable)

    @staticmethod
    def from_description(desc, callable=True):
        return Function(
            desc.ast,
            desc.name,
            desc.defaults,
            desc.globals,
            desc.module_infos,
            desc.module,
            callable=callable,
        )

    def compile(self):
        function_code = compile(self.tree, '<ast>', 'exec')

        namespace = {
            '__builtins__': __builtins__,
            **self.globals,
            **{
                alias: importlib.import_module(name)
                for alias, name in self.module_infos
            },
        }
        exec(function_code, namespace)
        f = namespace[self.name]

        return overwrite_globals(
            f,
            f.__globals__,
            defaults=self.defaults,
            module=self.module,
        )

    def __call__(self, *args, **kwargs):
        if self._func is None:
            self._func = self.compile()
        return self._func(*args, **kwargs)

    def __getstate__(self):
        return (
            self.tree,
            self.name,
            self.defaults,
            self.globals,
            self.module_infos,
            self.module,
            self.callable,
        )

    def __setstate__(self, state):
        self.tree = state[0]
        self.name = state[1]
        self.defaults = state[2]
        self.globals = state[3]
        self.module_infos = state[4]
        self.module = state[5]
        self.callable = state[6]
        self._func = None


class FunctionImage:
    def __init__(self, func_or_desc, attrs=None, deleted=frozenset()):
        self.keys = frozenset()
        if attrs is not None:
            for name, value in attrs.items():
                self.keys |= {name}
                super().__setattr__(name, value)

        self.desc = (
            func_or_desc if isinstance(func_or_desc, FunctionInfo)
            else describe(func_or_desc)
        )
        self.deleted = deleted
        self.ast = copy.deepcopy(self.desc.ast)
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
        return transformation(copy.deepcopy(self), *args, **kwargs)

    def assemble(self, *nodes):
        args = self.desc.ast.body[0].args

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

        f = Function(
            fdef,
            self.desc.name,
            self.desc.defaults,
            self.desc.globals,
            self.desc.module_infos,
            self.desc.module,
        )

        pickled = pickle.dumps(f)
        return pickle.loads(pickled)

        return f

    def update(self, deleted: List[str], new: Dict[str, Any], new_desc=None):
        for key in new.keys():
            if key in self.keys:
                raise AttributeError('Key {} already exists'.format(key))
        attrs = {
            **{ k: getattr(self, k)
                for k in self.keys
                if k not in deleted },
            **{ k: v
                for k, v in new.items()
                if k not in deleted },
        }
        new_deleted = self.deleted | frozenset(deleted)

        f = FunctionImage(
            new_desc if new_desc is not None else self.desc,
            attrs=attrs,
            deleted=new_deleted,
        )

        return f


def make_shared(func):
    return Function.from_function(func)
