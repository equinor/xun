from .blueprint import Blueprint
from .function_description import describe
from .function_image import FunctionImage
from .graph import CallNode
from . import transformations as xform
from abc import ABC
from abc import abstractmethod
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


def callnode_constructor(func):
    @FunctionImage.from_function
    def construct_callnode(*args, **kwargs):
        from xun.functions import CallNode
        return CallNode(func.name, func.hash, *args, **kwargs)
    return construct_callnode


class AbstractFunction(ABC):
    class FunctionCode:
        """FunctionCode

        Xun function code. Helper for checking/debugging generated code of
        xun function.
        """
        def __init__(self, func):
            self.owner = func

        @property
        def graph(self):
            source = astor.to_source(self.owner.graph_builder.tree)
            return FormatCode(source, style_config=adjusted_line_layout())[0]

        @property
        def task(self):
            source = astor.to_source(self.owner.callable.tree)
            return FormatCode(source, style_config=adjusted_line_layout())[0]

        @property
        def source(self):
            return self.owner.desc.src

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def hash(self):
        pass

    @property
    def code(self):
        return self.FunctionCode(self)

    @property
    @abstractmethod
    def dependencies(self):
        pass

    def sha256(self):
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
        sha256.update(self.desc.src.encode())
        for dependency in self.dependencies.values():
            if dependency is not self:
                sha256.update(dependency.hash.encode())
        truncated = sha256.digest()[:12]
        return base64.urlsafe_b64encode(truncated).decode()

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

    @property
    @abstractmethod
    def graph_builder(self):
        """graph builder

        Preparation step for Graph function. Build call graph for a call to
        this function

        Returns
        FunctionImage
            Serializable `FunctionImage` representation
        """
        pass

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
        return self.graph_builder(*args, **kwargs)

    @property
    @abstractmethod
    def callable(self):
        """Callable

        Creates a callable version of this function, usually executed by
        drivers. It is required to provide a store in extra_globals

        Returns
        -------
        FunctionImage
            Serializable callable function image
        """
        pass


class Function(AbstractFunction):
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
    callable()
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
        self._dependencies = dependencies
        self.interfaces = {}
        self.max_parallel = max_parallel
        self._hash = self.sha256()
        self._graph_builder = None
        self._callable = None

    @property
    def name(self):
        return self.desc.name

    @property
    def hash(self):
        return self._hash

    @property
    def dependencies(self):
        return self._dependencies

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

    @property
    def graph_builder(self):
        if self._graph_builder is None:
            deps = self.dependencies

            _, constants = xform.separate_constants(self.desc)
            sorted_constants, _ = xform.sort_constants(constants)
            copy_only = xform.copy_only_constants(sorted_constants, deps)
            unpacked = xform.unpack_unpacking_assignments(copy_only)
            xun_graph = xform.build_xun_graph(unpacked, deps)

            self._graph_builder = xform.assemble(self.desc, xun_graph)
        return self._graph_builder

    @property
    def callable(self):
        if self._callable is None:
            deps = self.dependencies

            head = xform.generate_header()
            body, constants = xform.separate_constants(self.desc)
            sorted_constants, _ = xform.sort_constants(constants)
            copy_only = xform.copy_only_constants(sorted_constants, deps)
            unpacked = xform.unpack_unpacking_assignments(copy_only)
            yields = xform.transform_yields(body, self.interfaces)
            load_from_store = xform.load_from_store(yields, unpacked, deps)

            f = xform.assemble(self.desc, head, load_from_store, yields)
            f.globals = {
                **{
                    name: value for name, value in self.desc.globals.items()
                    if not isinstance(value, AbstractFunction)
                },
                **{
                    name: callnode_constructor(f)
                    for name, f in self.dependencies.items()
                },
                **{
                    name: callnode_constructor(i)
                    for name, i in self.interfaces.items()
                }
            }
            f.hash = self.hash
            self._callable = f
        return self._callable

    def interface(self, func):
        interface_desc = describe(func)
        interface = Interface(self, interface_desc)
        self.interfaces[interface.name] = interface
        return interface


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


class Interface(AbstractFunction):
    """Interface

    """

    def __init__(self, target, desc):
        self.target = target
        self.desc = desc
        self._dependencies = {
            self.name: self,
            target.name: target,
        }
        self._hash = self.sha256()
        self._graph_builder = None
        self._callable = None

    @property
    def name(self):
        return self.desc.name

    @property
    def hash(self):
        return self._hash

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def globals(self):
        return {
            **{
                name: value for name, value in self.desc.globals.items()
                if not isinstance(value, AbstractFunction)
            },
            **{
                name: callnode_constructor(f)
                for name, f in self.dependencies.items()
            }
        }

    @property
    def graph_builder(self):
        if self._graph_builder is None:
            (interface_call,
             target_call,
            ) = xform.separate_interface_and_target(self.desc, self.target)
            interface = xform.build_interface_graph(interface_call,
                                                    target_call)

            f = xform.assemble(self.desc, interface)
            f.globals = self.globals
            self._graph_builder = f
        return self._graph_builder

    @property
    def callable(self):
        if self._callable is None:
            (interface_call,
             target_call,
            ) = xform.separate_interface_and_target(self.desc, self.target)
            interface = xform.interface_raise_on_execution(interface_call,
                                                           target_call)
            f = xform.assemble(self.desc, interface)
            f.globals = self.globals
            f.hash = self.hash
            self._callable = f
        return self._callable
