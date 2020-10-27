import networkx as nx
from .errors import CopyError
from .errors import NotDAGError


def sink_nodes(dag):
    """
    Given a directed acyclic graph, return a list of its sink nodes.
    """
    if not nx.is_directed_acyclic_graph(dag):
        raise NotDAGError
    return [n for n, out_degree in dag.out_degree() if out_degree == 0]


def source_nodes(dag):
    """
    Given a directed acyclic graph, return a list of it's sink nodes.
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
    args : lists of arguments
        the arguments of this call
    kwargs : mapping of str to arguments
        the keyword arguments of this call
    """
    def __init__(self, function_name, *args, **kwargs):
        self.function_name = function_name
        self.args = args
        self.kwargs = kwargs

    def __getitem__(self, key):
        return CallNodeSubscript(self, (key,))

    def __copy__(self):
        raise CopyError('Cannot copy value')

    def __deepcopy__(self, memo=None):
        raise CopyError('Cannot copy value')

    def __eq__(self, other):
        try:
            return (self.function_name == other.function_name
                and self.args == other.args
                and self.kwargs == other.kwargs)
        except AttributeError:
            return False

    def __hash__(self):
        return hash((
            self.function_name,
            tuple(self.args),
            frozenset(self.kwargs.items())
        ))

    def __repr__(self):
        args = [repr(self.function_name)]
        if len(self.args) > 0:
            args.append(', '.join(repr(a) for a in self.args))
        if len(self.kwargs) > 0:
            args.append(', '.join(
                '{}={}'.format(k, repr(v)) for k, v in self.kwargs.items()
            ))
        return 'CallNode({})'.format(', '.join(args))

    def unpack(self, shape, tupl_idx=()):
        """
        Given a tuple shape, the CallNode is unpacked into a tuple of
        CallNodeSubscripts with this shape.

        Examples
        --------

        >>> CallNode('f').unpack((1, (2,)))
        (
            CallNodeSubscript('f', (0,)),
            (
                CallNodeSubscript('f', (1, 0)),
                CallNodeSubscript('f', (1, 1))
            )
        )

        """
        if isinstance(shape, int):
            if shape == 0:
                local_tupl_idx = tupl_idx
                return CallNodeSubscript([self], local_tupl_idx)
            elif shape == 1:
                local_tupl_idx = tupl_idx
                return CallNodeSubscript(self, local_tupl_idx)
        else:
            if len(shape) == 1:
                inner_tuple = ()
                for s in range(shape[0]):
                    local_tupl_idx = tupl_idx + (s, )
                    inner_tuple += (CallNodeSubscript(self, local_tupl_idx), )
                return inner_tuple
            return_tuple = ()
            for idx, el in enumerate(shape):
                local_tupl_idx = tupl_idx + (idx, )
                return_tuple += (self.unpack(el, local_tupl_idx), )
            return return_tuple


class CallNodeSubscript:
    """CallNodeSubscript

    Representation of a subscripted CallNode.

    Attributes
    ----------
    call : CallNode
        the call that this representation is a subscript of
    subscript : tuple
        the subscript index

    """
    def __init__(self, call, subscript):
        self.call = call
        self.subscript = subscript

    def __getitem__(self, key):
        return CallNodeSubscript(self.call, self.subscript + (key,))

    def __hash__(self):
        return hash((
            self.call,
            self.subscript,
        ))

    def __eq__(self, other):
        return self.subscript == other.subscript and self.call == other.call

    def __repr__(self):
        return "CallNodeSubscript('{}', {})".format(
            self.call.function_name, self.subscript
        )
