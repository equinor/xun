from .blueprint import Blueprint
from .function_description import describe
from . import transformations

import ast


class Function:
    """
    TODO
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
    def from_function(func, max_parallel):
        desc = describe(func)
        dependencies = {
            g.name: g for g in desc.globals.values() if isinstance(g, Function)
        }

        f = Function(desc, dependencies, max_parallel)

        # Add f to it's dependencies, to allow recursive dependencies
        f.dependencies[f.name] = f

        return f

    def blueprint(self, *args, **kwargs):
        return Blueprint(self, *args, **kwargs)

    def graph(self, *args, **kwargs):
        if self._graph_builder is None:
            xun_function_names = frozenset(self.dependencies.keys())

            decomposed = (transformations.FunctionDecomposition(self.desc)
                .apply(transformations.separate_constants)
                .apply(transformations.sort_constants)
                .apply(transformations.copy_only_constants, xun_function_names)
                .apply(transformations.build_xun_graph, xun_function_names)
            )

            self._graph_builder = (decomposed
                .assemble(decomposed.xun_graph)
                .compile()
            )

        return self._graph_builder(*args, **kwargs)

    def callable(self, extra_globals=None):
        """Build serializable Function representations

        Given the description of a context function, sort and make constants
        copy only. Move constants to the top of the function body. Replace any
        context function calls within the with constants statement with loads
        from store. Assembles the final `Function` with constants first, and
        body after. A reference to the context store is injected into the
        globals of the function. This injection is the reason stores must be
        picklable.

        Parameters
        ----------
        context : xun.context
            The context owning the function
        func : xun.functions.FunctionDecomposition
            Description of the function to be built

        Returns
        -------
        xun.functions.Function
            The final representation of the function
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
    """

    TODO


    --------
    See also
    """
    def decorator(func):
        return Function.from_function(func, max_parallel)
    return decorator
