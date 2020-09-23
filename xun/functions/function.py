from .blueprint import Blueprint
from .function_description import describe
from . import transformations


class Function:
    """Function

    Xun functions. These are the distributed functions that xun executes. A xun
    function is typically created using the `@xun.function()` function
    decorator.

    Attributes
    ----------
    name : str
        The function name
    dependencies : mapping of function name to Function
        Dict holding the xun functions this one is dependent on


    Methods
    -------
    blueprint(*args, **kwargs)
        Creates xun blueprint representing a call to this function
    graph(*args, **kwargs)
        Creates a call graph for a call to this function
    callable(extra_globals=dict())
        Creates a callable version of this function, usually executed by
        drivers

    Examples
    --------

    Create and run a blueprint for a xun function

    >>> @xun.function()
    ... def f(a, b):
    ...     return a + b
    ...
    >>> blueprint = f.blueprint(1, 2)
    >>> blueprint.run(
    ...     driver=xun.functions.driver.Sequential(),
    ...     store=xun.functions.store.Memory(),
    ... )
    3

    See Also
    --------
    Blueprint : Essentially the plan to be executed
    function : Function decorator to create xun functions
    """

    def __init__(self, desc, dependencies, max_parallel):
        self.desc = desc
        self.dependencies = dependencies
        self.max_parallel = max_parallel
        self._graph_builder = None

    @property
    def name(self):
        return self.desc.name

    @staticmethod
    def from_function(func, max_parallel=None):
        """From Function

        Creates a xun function from a python function

        Parameters
        ----------
        func : python function
            The function definition to create the xun function from
        max_parallel : int
            The maximum parallel jobs allowed for this function

        Returns
        -------
        Function
            The `Function` representation of the given function
        """
        if max_parallel is not None:
            msg = 'Limiting parallel execution not yet implemented'
            raise NotImplementedError(msg)

        desc = describe(func)
        dependencies = {
            g.name: g for g in desc.globals.values() if isinstance(g, Function)
        }

        f = Function(desc, dependencies, max_parallel)

        # Add f to it's dependencies, to allow recursive dependencies
        f.dependencies[f.name] = f

        return f

    def blueprint(self, *args, **kwargs):
        """Blueprint

        Create a blueprint for a call to this function

        Parameters
        ----------
        *args
        **kwargs

        Returns
        -------
        Blueprint
            Blueprint representing the call to this function

        See Also
        --------
        Blueprint : Comprises the call, call graph, and required functions
        """
        return Blueprint(self, *args, **kwargs)

    def graph(self, *args, **kwargs):
        """Graph

        Build call graph for a call to this function

        Parameters
        ----------
        *args
        **kwargs

        Returns
        nx.DiGraph
            The call graph for the call
        """
        if self._graph_builder is None:
            xun_function_names = frozenset(self.dependencies.keys())

            decomposed = (transformations.FunctionDecomposition(self.desc)
                .apply(transformations.separate_constants)
                .apply(transformations.sort_constants)
                .apply(transformations.copy_only_constants, xun_function_names)
                .apply(transformations.build_xun_graph, xun_function_names)
            )

            self._graph_builder = decomposed.assemble(decomposed.xun_graph)

        return self._graph_builder(*args, **kwargs)

    def callable(self, extra_globals=None):
        """Callable

        Creates a callable version of this function, usually executed by
        drivers. It is required to provide a store in extra_globals

        Parameters
        ----------
        extra_globals : dict
            Mapping names to any references that should be made available to
            the callable. A reference named `'_xun_store'` pointing to a
            `Store` is required to be able to execute the callable. Any globals
            provided should be picklable if the function is intended to be
            serialized

        Returns
        -------
        FunctionImage
            Serializable callable function image

        See Also
        --------
        Store : xun store
        """
        xun_function_names = frozenset(self.dependencies.keys())

        fimg = (transformations.FunctionDecomposition(self.desc)
            .apply(transformations.separate_constants)
            .apply(transformations.sort_constants)
            .apply(transformations.copy_only_constants, xun_function_names)
            .apply(transformations.load_from_store, xun_function_names)
        )

        f = fimg.assemble(fimg.load_from_store, fimg.body)

        # Remove any refernces to function dependencies, they may be
        # unpicklable and their code has been replaced
        new_globals = {
            name: value for name, value in fimg.desc.globals.items()
            if not isinstance(value, Function)
        }
        if extra_globals is not None:
            new_globals.update(extra_globals)

        f.globals = new_globals

        return f


def function(max_parallel=None):
    """xun.function

    Function decorator used to create xun functions from python functions

    Examples
    --------

    >>> @xun.function()
    ... def get_a():
    ...     return 'a'
    ...
    >>> @xun.function()
    ... def get_b():
    ...     return 'b'
    ...
    >>> @xun.function
    ... def workflow(prefix):
    ...     return prefix + a + b
    ...     with ...:
    ...         a = get_a()
    ...         b = get_b()
    ...
    >>> blueprint = workflow.blueprint('result_')
    >>> blueprint.run(
    ...     driver=xun.functions.driver.Sequential(),
    ...     store=xun.functions.store.Memory(),
    ... )
    'result_ab'

    Returns
    -------
    Function
        xun function created from the decorated function
    """
    def decorator(func):
        return Function.from_function(func, max_parallel)
    return decorator
