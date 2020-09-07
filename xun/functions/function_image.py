from .function_description import describe
from .util import overwrite_globals
import importlib


class FunctionImage:
    """FunctionImage

    Python functions are only pickleable if they are top-level defined in module
    installed on the serializing and deserializing systems. This is a
    representation of functions that can be pickled and unpickled even if the
    function is not known to the deserializing system, or even the serializing
    system.

    FunctionImage object are how functions are communicated and stored in xun
    projects. If a context function calls an external function not installed on
    the system, they need to be represented as a FunctionImage object, to do
    this, the xun.make_shared function decorator can be used.

    Attributes
    ----------
    tree : ast.Module
        The syntax tree of the function
    name : str
        FunctionImage name
    defaults
        The original function's default arguments values
    globals : dict
        The original function's globals filtered so that this object can be
        pickled.
    module_infos : dict
        mapping external_names used by the function that reference modules. The
        dict keys are the names used by the function, while the values are
        actual module names.
    module : str
        Name of the module that this function lives in
    _func : function
        Cached compiled function. _func is not pickled.

    Examples
    --------

    Create a FunctionImage from a python function

    >>> def f(a, b):
    ...     return a + b
    ...
    >>> F = FunctionImage.from_function(f)
    >>> pickled = pickle.dumps(F)
    >>> g = pickle.loads(pickled)
    >>> f(1, 2) == g(1, 2)
    True

    Create a FunctionImage using the `xun.make_shared` function decorator

    >>> @xun.make_shared
    ... def f(a, b):
    ...     return a + b
    ...
    >>> f(1, 2)
    3

    See Also
    --------
    xun.make_shared : stores a function as a FunctionImage object
    """
    def __init__(self,
                 tree,
                 name,
                 defaults,
                 globals,
                 module_infos,
                 module):
        self.tree = tree
        self.name = name
        self.defaults = defaults
        self.globals = globals
        self.module_infos = module_infos
        self.module = module
        self._func = None

    @staticmethod
    def from_function(func):
        """FunctionImage from a function

        Create FunctionImage from a python function

        Parameters
        ----------
        func : function
            The function to represent as a FunctionImage object
        callable : bool
            Whether or not the resulting object should be callable

        Returns
        -------
        FunctionImage
            Serializable representation of the given function
        """
        desc = describe(func)
        return FunctionImage.from_description(desc)

    @staticmethod
    def from_description(desc):
        """FunctionImage from description

        Create FunctionImage from function description

        Parameters
        ----------
        desc : xun.functions.FunctionDescription
            FunctionImage description
        callable : bool
            Whether or not the resulting object should be callable

        Returns
        -------
        FunctionImage
            Serializable representation of the described function
        """
        return FunctionImage(
            desc.ast,
            desc.name,
            desc.defaults,
            desc.globals,
            desc.module_infos,
            desc.module,
        )

    def compile(self):
        """Compile

        Compile a runnable python function from this FunctionImage object

        Returns
        -------
        function
            Python function
        """
        function_code = compile(self.tree, '<ast>', 'exec')

        namespace = {
            '__builtins__': __builtins__,
            **self.globals,
            **{
                alias: importlib.import_module(name)
                for alias, name in self.module_infos.items()
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
        """
        Compile and run the function represented by this object. The compiled
        function is cached
        """
        if self._func is None:
            self._func = self.compile()
        return self._func(*args, **kwargs)

    def __getstate__(self):
        """
        Controls how FunctionImage objects are pickled. We store everything
        except the cached compiled function `_func`.
        """
        return (
            self.tree,
            self.name,
            self.defaults,
            self.globals,
            self.module_infos,
            self.module,
        )

    def __setstate__(self, state):
        """
        Controls how FunctionImage objects are unpickled. We store everything
        except the cached compiled function `_func`.
        """
        self.tree = state[0]
        self.name = state[1]
        self.defaults = state[2]
        self.globals = state[3]
        self.module_infos = state[4]
        self.module = state[5]
        self._func = None


def make_shared(func):
    """ Make shared function decorator

    FunctionImage decorator to make a non-installed function serializable and
    callable by context functions.

    Examples
    --------

    >>> @xun.make_shared
    ... def f(a, b):
    ...     return a + b
    ...
    >>> f(1, 2)
    3

    See Also
    --------
    xun.functions.FunctionImage : Serializable representation python functions
    """
    return FunctionImage.from_function(func)
