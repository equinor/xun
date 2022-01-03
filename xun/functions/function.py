from . import transformations as xform
from .blueprint import Blueprint
from .errors import XunSyntaxError
from .function_description import describe
from .graph import CallNode
from .util import func_arg_names
from abc import ABC
from abc import abstractmethod
from itertools import chain
from yapf.yapflib.style import CreatePEP8Style
from yapf.yapflib.yapf_api import FormatCode
import astor
import base64
import copy
import hashlib
import shutil


def adjusted_line_layout(style=CreatePEP8Style()):
    columns = shutil.get_terminal_size().columns
    style['COLUMN_LIMIT'] = columns
    return style


class SymbolicFunction:
    def __init__(self, name, hash):
        self.name = name
        self.hash = hash

    def __call__(self, *args, **kwargs):
        return self.callnode(*args, **kwargs)

    def callnode(self, *args, **kwargs):
        from xun.functions import CallNode
        return CallNode(self.name, self.hash, *args, **kwargs)


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

    def __call__(self, *args, **kwargs):
        raise XunSyntaxError(f'xun functions, like {self.name}, can only be '
                             'called from xun definitions statements.')

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
    def globals(self):
        pass

    @property
    @abstractmethod
    def dependencies(self):
        pass

    def sha256(self):
        """SHA256

        Calculate a hash identifier for a function with the given description
        and dependencies.

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
        -------
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
        self.worker_resources = {}
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
                name: SymbolicFunction(f.name, f.hash)
                for name, f in chain(self.dependencies.items(),
                                     self.interfaces.items())
            },
        }

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
            g.name: g
            for g in desc.globals.values()
            if isinstance(g, AbstractFunction)
        }

        f = Function(desc, dependencies, max_parallel)

        # Add f to it's dependencies, to allow recursive dependencies
        f.dependencies[f.name] = f

        return f

    @property
    def graph_builder(self):
        if self._graph_builder is None:
            _, constants = xform.separate_constants(self.desc)
            sorted_constants, _ = xform.sort_constants(constants)
            pass_by_value = xform.pass_by_value(sorted_constants)
            unpacked = xform.unpack_unpacking_assignments(pass_by_value)
            xun_graph = xform.build_xun_graph(unpacked)

            self._graph_builder = xform.assemble(
                self.desc,
                xun_graph,
                globals=self.globals,
                hash=self.hash,
                original_source_code=self.code.source,
                interface_hashes=frozenset(
                    i.hash for i in self.interfaces.values()
                ),
            )
        return self._graph_builder

    @property
    def callable(self):
        if self._callable is None:
            arg_names = func_arg_names(self.desc.ast.body[0])

            head = xform.generate_header()
            body, constants = xform.separate_constants(self.desc)
            sorted_constants, _ = xform.sort_constants(constants)
            pass_by_value = xform.pass_by_value(sorted_constants)
            unpacked = xform.unpack_unpacking_assignments(pass_by_value)
            load_args = xform.load_args(body, arg_names)
            yields = xform.transform_yields(load_args, arg_names)
            load_constants = xform.load_constants(yields, unpacked)

            self._callable = xform.assemble(
                self.desc,
                head,
                load_constants,
                yields,
                globals=self.globals,
                hash=self.hash,
                original_source_code=self.code.source,
                interface_hashes=frozenset(
                    i.hash for i in self.interfaces.values()
                ),
        )
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


def worker_resource(res_type, number):
    """ Worker resource function decorator

    Function decorator used to specify resources that should be allocated

    Examples
    --------

    >>> @xun.worker_resource('MEMORY', 10e2)
    ... @xun.function()
    ... def ftest():
    ...     return 'test'
    ...

    """
    def decorator(func):
        func_prime = copy.deepcopy(func)
        func_prime.worker_resources[res_type] = number
        return func_prime
    return decorator


class Interface(AbstractFunction):
    """Interface

    """

    def __init__(self, target, desc):
        self.target = target
        self.desc = desc
        self.worker_resources = {}
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
                name: SymbolicFunction(f.name, f.hash)
                for name, f in self.dependencies.items()
            },
        }

    @property
    def graph_builder(self):
        if self._graph_builder is None:
            (interface_call,
             target_call,
            ) = xform.separate_interface_and_target(self.desc, self.target)
            interface = xform.build_interface_graph(interface_call,
                                                    target_call)
            self._graph_builder = xform.assemble(self.desc,
                                                 interface,
                                                 globals=self.globals,
                                                 hash=self.hash)
        return self._graph_builder

    @property
    def callable(self):
        if self._callable is None:
            (interface_call,
             target_call,
            ) = xform.separate_interface_and_target(self.desc, self.target)
            interface = xform.interface_raise_on_execution(interface_call,
                                                           target_call)
            self._callable = xform.assemble(self.desc,
                                            interface,
                                            globals=self.globals,
                                            hash=self.hash)
        return self._callable
