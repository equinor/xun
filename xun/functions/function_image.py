from .functions import describe
from .functions import FunctionInfo
from .functions import overwrite_globals
from itertools import chain
from typing import Any
from typing import Dict
from typing import List
import ast
import copy


class Function:
    def __init__(self, tree, name, globals, defaults, module):
        self.tree = tree
        self.name = name
        self.globals = globals
        self.defaults = defaults
        self.module = module

    def compile(self):
        function_code = compile(self.tree, '<string>', 'exec')

        namespace = {}
        exec(function_code, namespace)
        f = namespace[self.name]

        function_globals = {
            '__builtins__': __builtins__,
            **self.globals,
        }

        return overwrite_globals(
            f,
            function_globals,
            defaults=self.defaults,
            module=self.module,
        )


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
        return transformation(copy.deepcopy(self), *args, **kwargs)

    def assemble(self, *nodes):
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

        return Function(
            fdef,
            self.desc.name,
            self.desc.globals,
            self.desc.defaults,
            self.desc.module
        )

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
