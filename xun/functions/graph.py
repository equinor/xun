from .errors import CopyError
from .errors import NotDAGError
from .util import make_hashable
import contextvars
import networkx as nx


def sink_nodes(dag):
    """
    Given a directed acyclic graph, return a list of its sink nodes.
    """
    if not nx.is_directed_acyclic_graph(dag):
        raise NotDAGError
    return [n for n, out_degree in dag.out_degree() if out_degree == 0]


def source_nodes(dag):
    """
    Given a directed acyclic graph, return a list of it's source nodes.
    """
    if not nx.is_directed_acyclic_graph(dag):
        raise NotDAGError
    return [n for n, in_degree in dag.in_degree() if in_degree == 0]


class CallNode:
    """CallNode

    Representaion of a call that is to be executed. These are used to represent
    entry points, the calls in the call graph, and are the keys used in the
    store. When a call is executed, the result is stored in the program store
    using the CallNode as key.

    CallNodes are used as sentinel values during scheduling. To protect against
    attempted modification during scheduling, copying of CallNodes is
    disallowed. This is because the value a CallNode represents is not known
    until execution and can therefore not be used.

    Attributes
    ----------
    function_name : str
        name of the function this representation is a call to
    function_hash : bytes
        SHA256 identifier of the function
    args : lists of arguments
        the arguments of this call
    kwargs : mapping of str to arguments
        the keyword arguments of this call
    """
    class _deepcopy_context:
        """
        `deepcopy` has different effects on callnode depending on the context
        it is run in.

        When setting the behavior of deepcopy for CallNodes, set
        `CallNode._deepcopy_context.value` to a generator function within a
        local context. The generator function should yield exactly one value.
        Any code following the yield statement is executed when we leave the
        node.

        - Default
            The default behavior when copying a call node is to raise a
            CopyError. This is because passing arguments to non xun functions
            from within a xun definitions statement is done by copying. Passing
            a call node to a non xun function is not possible, so we raise an
            error.
        - Loading
            The mechanics of replacing call nodes inside xun functions with
            their results are through deepcopy. The context should then be set
            to replace any copied call node with a result loaded from the
            store.
        - Dependency detection
            Dependencies between xun function calls inside a xun definition
            statement are discovered by doing a depth first search through
            deepcopy.

        See Also
        --------
        load_results_by_deepcopy : replaces CallNode instances with results
        resolve_args_by_deepcopy : replaces CallNode instances with results
        detect_dependencies_by_deepcopy :
            depth first search for dependency detection
        """
        @staticmethod
        def _default_deepcopy_context(callnode, memo):
            raise CopyError(callnode, 'CallNode copied without context')

        value = contextvars.ContextVar(
            '_deepcopy_context_value', default=_default_deepcopy_context)

    def __init__(self, function_name, function_hash, *args, **kwargs):
        self.function_name = function_name
        self.function_hash = function_hash
        self.subscript = ()
        self.args = make_hashable(args)
        self.kwargs = make_hashable(kwargs)

    def __getitem__(self, key):
        return self._replace(subscript=self.subscript + (key,))

    def __iter__(self):
        raise TypeError('Cannot iterate xun function results at schedule time')

    def __copy__(self):
        raise CopyError('Copying of callnodes is internally used by xun to '
                        'detect call graphs. A regular copy of a callnode '
                        'is usually an indication of an error.')

    def __deepcopy__(self, memo):
        """
        deepcopy of Callnodes are only allowed when used internally by xun
        """
        deepcopy_impl = CallNode._deepcopy_context.value.get()(self, memo)
        copied = next(deepcopy_impl)
        try:
            next(deepcopy_impl)
        except StopIteration:
            return copied
        else:
            raise CopyError('callnode deepcopy did not exit as expected')

    def __eq__(self, other):
        try:
            return (self.function_name == other.function_name
                and self.function_hash == other.function_hash
                and self.subscript == other.subscript
                and self.args == other.args
                and self.kwargs == other.kwargs)
        except AttributeError:
            return False

    def __hash__(self):
        return hash((
            self.function_name,
            self.function_hash,
            self.subscript,
            tuple(self.args),
            frozenset(self.kwargs.items())
        ))

    def __repr__(self):
        args = [repr(self.function_name), repr(self.function_hash)]
        if len(self.args) > 0:
            args.append(', '.join(repr(a) for a in self.args))
        if len(self.kwargs) > 0:
            args.append(', '.join(
                '{}={}'.format(k, repr(v)) for k, v in self.kwargs.items()
            ))
        subscript = ''.join(f'[{s}]' for s in self.subscript)
        return f'CallNode({", ".join(args)}){subscript}'

    def _replace(self, **kwargs):
        """
        Replace the existing values of class attributes with new ones.

        Parameters
        ----------
        kwargs : dict
            keyword arguments corresponding to one or more attributes whose
            values are to be modified

        Returns
        -------
        A new CallNode with replaced attributes
        """
        attribs = {k: kwargs.pop(k, v) for k, v in vars(self).items()}
        if kwargs:
            raise ValueError(f'Got unexpected field names: {list(kwargs)!r}')
        inst = CallNode.__new__(CallNode)
        inst.__dict__.update(attribs)
        return inst
