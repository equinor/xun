from .functions import describe
from .functions import FunctionInfo
from .functions import overwrite_globals
from itertools import chain
from typing import Any
from typing import Dict
from typing import List
import ast
import copy
import importlib
import pickle


class Function:
    """Function

    Python functions are only pickleable if they are top-level defined in module
    installed on the serializing and deserializing system. This is a
    representation of functions that can be pickled and unpickled even if the
    function is not known to the deserializing system, or even the serializing
    system.

    Function object are how functions are communicated and stored in xun
    projects. If a context function calls an external function not installed on
    the system, they need to be represented as a Function object, to do this,
    the xun.make_shared function decorator can be used.

    Attributes
    ----------
    tree : ast.Module
        The syntax tree of the function
    name : str
        Function name
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
    callable : boolean
        Whether this object should be callable or not
    _func : function
        Cached compiled function. _func is not pickled.

    Examples
    --------

    Create a Function from a python function

    >>> def f(a, b):
    ...     return a + b
    ...
    >>> F = Function.from_function(f)
    >>> pickled = pickle.dumps(F)
    >>> g = pickle.loads(pickled)
    >>> f(1, 2) == g(1, 2)
    True

    Create a Function using the `xun.make_shared` function decorator

    >>> @xun.make_shared
    ... def f(a, b):
    ...     return a + b
    ...
    >>> f.name, f.callable
    ('f', True)
    >>> f(1, 2)
    3

    See Also
    --------
    xun.make_shared : stores a function as a Function object
    """
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
        """Function from a function

        Create Function from a python function

        Parameters
        ----------
        func : function
            The function to represent as a Function object
        callable : bool
            Whether or not the resulting object should be callable

        Returns
        -------
        Function
            Serializable representation of the given function
        """
        desc = describe(func)
        return Function.from_description(desc, callable=callable)

    @staticmethod
    def from_description(desc, callable=True):
        """Function from description

        Create Function from function description

        Parameters
        ----------
        desc : xun.functions.FunctionInfo
            Function description
        callable : bool
            Whether or not the resulting object should be callable

        Returns
        -------
        Function
            Serializable representation of the described function
        """
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
        """Compile

        Compile a runnable python function from this Function object

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
        Controls how Function objects are pickled. We store everything except
        the cached compiled function `_func`.
        """
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
        """
        Controls how Function objects are unpickled. We store everything except
        the cached compiled function `_func`.
        """
        self.tree = state[0]
        self.name = state[1]
        self.defaults = state[2]
        self.globals = state[3]
        self.module_infos = state[4]
        self.module = state[5]
        self.callable = state[6]
        self._func = None


class FunctionImage:
    """ FunctionImage

    Immutable decomposition of a function. Instance of FunctionImage are used to
    transform functions as represented by syntax trees.

    Methods
    -------
    apply(transform, *args, **kwargs)
        Apply transform and return new FunctionImage
    assemble(*nodes)
        Assemble FunctionImage into Function object with the given function body
        ast.AST nodes.
    update(deleted, new, new_desc)
        Create a new FunctionImage object with the given changes

    Examples
    --------

    Apply transformations to a FunctionImage

    >>> def func():
    ...     return 1
    ...     return 2
    ...
    >>> def transformation(img: FunctionImage):
    ...     # remove first return
    ...     cropped_ast = img.ast.body[0].body[:1]
    ...     return img.update(
    ...         # Delete the original ast from FunctionImage
    ...         ['ast'],
    ...         {
    ...             # Add cropped_ast as attribute
    ...             'cropped_ast': cropped_ast,
    ...         }
    ...     )
    ...
    >>> img = FunctionImage(func)
    >>> transformed = img.apply(transformation)
    >>> f = img.assemble(img.ast.body[0].body)
    >>> g = transformed.assemble(transformed.cropped_ast)
    >>> f()
    1
    >>> g()
    2
    """
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
        """Apply transformation

        Parameters
        ----------
        transformation : callable
            Callable that takes a FunctionImage, computes new attributes and
            returns a new, updated FunctionImage. This is typically a function
            of the following form::

                def transform(image: FunctionImage) -> FunctionImage:
                    ...
                    return image.update(
                        deleted_attributes,
                        new_attributes,
                    )
        *args
            Arguments to pass to the transformation function
        **kwargs
            Keyword arguments to pass to the transformation function

        Returns
        -------
        FunctionImage
            The transformed function image
        """
        return transformation(copy.deepcopy(self), *args, **kwargs)

    def assemble(self, *nodes):
        """Assemble serializable `Function` representation

        Takes a list of lists of statements and assembles a serializable
        `Function` object.

        Parameters
        ----------
        *nodes : vararg of list of ast.AST nodes
            lists of statements (in order) to be used as the statements of the
            generated function body

        Returns
        -------
        Function
            Serializable `Function` representation
        """
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
        """Update

        Create a new FunctionImage object with the given changes

        Parameters
        ----------
        deleted : List of str
            List of fields to be permanently removed from the FunctionImage.
            No attribute using the same name can be used again. This is done to
            make permanent changes to FunctionImages, so that laters calls
            cannot add to a previously modified section of the code
        new : Mapping from str to Any
            Dictionary containing the new fields to be added to the
            FunctionImage
        new_desc : xun.functions.FunctionInfo, optional
            use with care, replaces the underlying function description

        Returns
        -------
        Function
            The updated FunctionImage
        """
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
    """ Make shared function decorator

    Function decorator to make a non-installed function serializable and
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
    xun.functions.Function : Serializable representation python functions
    """
    return Function.from_function(func)
