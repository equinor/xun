from .functions import describe
from .program import Compiler
from collections import namedtuple


class context:
    def __init__(ctx, driver, store):
        ctx.functions = {}
        ctx.driver = driver
        ctx.store = store

    def __contains__(ctx, name):
        return name in ctx.functions

    def __getitem__(self, key):
        return self.functions[key]

    def __getattr__(ctx, name):
        if name in ctx.functions:
            return ctx.entry(name)
        return super(context, ctx).__getattribute__(name)

    def entry(ctx, name):
        return Compiler(ctx, name)

    def function(ctx, max_parallel=None):
        class function_decorator:
            def __init__(self, func):
                self.func = func
                self.desc = describe(func)
                self.name = self.desc.name
                ctx.register(func, self.desc)

            def __call__(self, *args, **kwargs):
                raise NotImplementedError()
        return function_decorator

    def register(ctx, func, desc):
        ctx.functions[desc.name] = ContextEntry(desc=desc, func=func)


ContextEntry = namedtuple(
    'ContextEntry',
    [
        'desc',
        'func',
    ]
)
