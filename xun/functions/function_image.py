from .function_description import describe
import functools
import importlib


class FunctionImage:
    """FunctionImage

    Python functions are only picklable if they are top-level defined in module
    installed on the serializing and deserializing systems. A FunctionImage is
    a representation of functions that can be pickled and unpickled even if the
    function does not originally exist on the deserializing system, or even the
    serializing system.

    FunctionImage objects are how functions are communicated and stored in xun
    projects. If a FunctionImage refers to a function that isn't installed,
    that function should also be represented as a FunctionImage. This can be
    achieved using the `xun.make_shared` function decorator.

    Attributes
    ----------
    tree : ast.Module
        The syntax tree of the function
    name : str
        FunctionImage name
    globals : dict
        The original function's globals filtered so that this object can be
        pickled.
    referenced_modules : dict
        The dict keys are the names used by the function, while the values are
        actual module names.
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
                 qualname,
                 doc,
                 annotations,
                 module_name,
                 globals,
                 referenced_modules,
                 hash=None):
        self.tree = tree
        self.__name__ = name
        self.__qualname__ = qualname
        self.__doc__ = doc
        self.__annotations__ = annotations
        self.__module__ = module_name
        self.globals = globals
        self.referenced_modules = referenced_modules
        self.hash = hash
        self._func = None

    @staticmethod
    def from_function(func, hash=None):
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
        return FunctionImage.from_description(desc, hash=hash)

    @staticmethod
    def from_description(desc, hash=None):
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
            desc.qualname,
            desc.doc,
            desc.annotations,
            desc.module,
            desc.globals,
            desc.referenced_modules,
            hash=hash,
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
                m.asname: importlib.import_module(m.module)
                for m in self.referenced_modules
            },
        }
        exec(function_code, namespace)  # nosec
        f = namespace[self.name]

        functools.update_wrapper(f, self)

        return f

    @property
    def name(self):
        return self.__name__

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
            self.__name__,
            self.__qualname__,
            self.__doc__,
            self.__annotations__,
            self.__module__,
            self.globals,
            self.referenced_modules,
            self.hash,
        )

    def __setstate__(self, state):
        """
        Controls how FunctionImage objects are unpickled. We store everything
        except the cached compiled function `_func`.
        """
        self.tree = state[0]
        self.__name__ = state[1]
        self.__qualname__ = state[2]
        self.__doc__ = state[3]
        self.__annotations__ = state[4]
        self.__module__ = state[5]
        self.globals = state[6]
        self.referenced_modules = state[7]
        self.hash = state[8]
        self._func = None


def make_shared(func):
    """ Make shared function decorator

    FunctionImage decorator to make a non-installed function serializable and
    callable by xun functions.

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
