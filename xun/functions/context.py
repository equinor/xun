from .function_image import Function
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
        if name in super(context, ctx).__getattribute__('functions'):
            return ctx.entry(name)
        return super(context, ctx).__getattribute__(name)

    def entry(ctx, name):
        return Compiler(ctx, name)

    def function(ctx, max_parallel=None):
        def function_decorator(func):
            desc = describe(func)
            ctx.register(func.__name__, desc)
            return Function.from_description(desc, callable=False)
        return function_decorator

    def register(ctx, name, desc):
        ctx.functions[name] = desc
