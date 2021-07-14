from .blueprint import Blueprint
from .function_description import describe
from .graph import CallNode
from . import transformations as xform
from yapf.yapflib.yapf_api import FormatCode
from yapf.yapflib.style import CreatePEP8Style
import astor
import base64
import hashlib
import shutil


def adjusted_line_layout(style=CreatePEP8Style()):
    columns = shutil.get_terminal_size().columns
    style['COLUMN_LIMIT'] = columns
    return style


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

    class FunctionCode:
        """FunctionCode

        Xun function code. Helper for checking/debugging generated code of
        xun function.
        """
        def __init__(self, func):
            self.owner = func

        @property
        def graph(self):
            return self.owner.createGraphBuilder().tree

        @property
        def graph_str(self):
            source = astor.to_source(self.graph)
            return FormatCode(source, style_config=adjusted_line_layout())[0]

        @property
        def task(self):
            return self.owner.callable().tree

        @property
        def task_str(self):
            source = astor.to_source(self.task)
            return FormatCode(source, style_config=adjusted_line_layout())[0]

        @property
        def source(self):
            return self.owner.desc.ast

        @property
        def source_str(self):
            return self.owner.desc.src

    def __init__(self, desc, dependencies, max_parallel):
        self.desc = desc
        self.dependencies = dependencies
        self.max_parallel = max_parallel
        self.hash = Function.sha256(desc, dependencies)
        self._graph_builder = None
        self.code = self.FunctionCode(self)

    @property
    def name(self):
        return self.desc.name

    @staticmethod
    def sha256(desc, dependencies):
        """SHA256

        Calculate a hash identifier for a function with the given description
        and dependencies.

        Parameters
        ----------
        desc : xun.functions.FunctionDescription
            Description of the hashed function
        dependencies : mapping of name to Function
            The dependencies of the hashed function

        Returns
        -------
        str
            Hex digest of function hash
        """
        sha256 = hashlib.sha256()
        sha256.update(desc.src.encode())
        for dependency in dependencies.values():
            sha256.update(dependency.hash.encode())
        truncated = sha256.digest()[:12]
        return base64.urlsafe_b64encode(truncated).decode()

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

    def callnode(self, *args, **kwargs):
        """Call Node

        Create a CallNode for a call to this function

        Parameters
        ----------
        *args
        **kwargs

        Returns
        -------
        CallNode
            CallNode representing a call to this function

        See Also
        --------
        CallNode : Symbolic representation of a call to this function
        """
        return CallNode(self.name, self.hash, *args, **kwargs)

    def createGraphBuilder(self):
        """CreateGraphBuilder

        Preparation step for Graph function. Build call graph for a call to
        this function

        Returns
        FunctionImage
            Serializable `FunctionImage` representation
        """
        if self._graph_builder is None:
            deps = self.dependencies
            _, constants = xform.separate_constants(self.desc)
            sorted_constants, _ = xform.sort_constants(constants)
            copy_only = xform.copy_only_constants(sorted_constants, deps)
            unpacked = xform.unpack_unpacking_assignments(copy_only)
            xun_graph = xform.build_xun_graph(unpacked, deps)
            self._graph_builder = xform.assemble(self.desc, xun_graph)
        return self._graph_builder

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
        return self.createGraphBuilder()(*args, **kwargs)

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
        deps = self.dependencies
        body, constants = xform.separate_constants(self.desc)
        sorted_constants, _ = xform.sort_constants(constants)
        copy_only = xform.copy_only_constants(sorted_constants, deps)
        unpacked = xform.unpack_unpacking_assignments(copy_only)
        load_from_store = xform.load_from_store(body, unpacked, deps)
        f = xform.assemble(self.desc, load_from_store, body)

        # Remove any refernces to function dependencies, they may be
        # unpicklable and their code has been replaced
        new_globals = {
            name: value for name, value in self.desc.globals.items()
            if not isinstance(value, Function)
        }
        if extra_globals is not None:
            new_globals.update(extra_globals)

        f.globals = new_globals
        f.hash = self.hash

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
