from .function_image import Function
from .functions import describe
from .program import Compiler
from collections import namedtuple


class context:
    """context

    Contexts are used to build xun programs

    Attributes
    ----------
    functions : dict
        Dictionary mapping function names to function descriptions
    driver : xun.functions.driver.Driver
        The driver that will execute programs compiled from this context
    store : xun.functions.store.Store
        The store that to be used when executing programs

    Examples
    --------

    Use a context to create and execute a program

    >>> import xun
    >>> context = xun.context(
    ...     driver = xun.functions.driver.Sequential(),
    ...     store = xun.functions.store.Memory(),
    ... )
    >>> @context.function()
    ... def xun_name():
    ...     return 'Xun'
    ...
    >>> @context.function()
    ... def greet(prefix):
    ...     print('{} {}!'.format(prefix, name))
    ...     with ...:
    ...         name = xun_name()
    ...
    >>> program = context.greet.compile('Hello')
    >>> program()
    'Hello Xun!'
    """
    def __init__(ctx, driver, store):
        ctx.functions = {}
        ctx.driver = driver
        ctx.store = store

    def __contains__(ctx, name):
        return name in ctx.functions

    def __getitem__(self, key):
        return self.functions[key]

    def __getattr__(ctx, name):
        """
        Return either context attribute or a compiler with entry as the given
        attribute name.

        See Also
        --------
        context.entry
        """
        if name in super(context, ctx).__getattribute__('functions'):
            return ctx.entry(name)
        return super(context, ctx).__getattribute__(name)

    def entry(ctx, name):
        """Entry

        Return a Compiler for an entrypoint

        Parameters
        ----------
        name : str
            The name of the context function to use as entry point

        Returns
        -------
        xun.functions.program.Compiler
            Compiler object that can build programs

        Examples
        --------

        Compile a program with entry point ``start`` and arguments 1, 2

        >>> program = some_ctx.entry('start').compile(1, 2)
        >>> program() # runs the compiled program

        """
        return Compiler(ctx, name)

    def function(ctx, max_parallel=None):
        """context.function()

        Function decorator that will register a the function as a job within
        this context. This is how jobs in xun are specified

        Parameters
        ----------
        max_parallel : int, optional
            The maximum number of workers that should run this job in parallel.

        Returns
        -------
        function_decorator
            The function will be replaced by a `xun.functions.Function`
            representing the input function, flagged as non-callable. The
            should only be called from programs compiled by this context

        Examples
        --------

        create a context function that will live within context_object that will
        run at most 2 in parallel.

        >>> @context_object.function(max_parallel=2)
        ... def some_job(args):
        ...     return process(args)
        ...
        """
        def function_decorator(func):
            desc = describe(func)
            ctx.register(func.__name__, desc)
            return Function.from_description(desc, callable=False)
        return function_decorator

    def register(ctx, name, desc):
        ctx.functions[name] = desc
