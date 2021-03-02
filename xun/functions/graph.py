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

    def unpack(self, shape, *, _subscript=()):
        """
        Unpacks a CallNode into a tuple of CallNodeSubscripts with a given
        shape using recursion. Every CallNodeSubscript holds the parent
        CallNode along with its respective subscript index.

        Examples
        --------
        >>> CallNode('f').unpack((2, (2,)))
        (
            CallNodeSubscript('f', (0,)),
            CallNodeSubscript('f', (1,)),
            (
                CallNodeSubscript('f', (2, 0)),
                CallNodeSubscript('f', (2, 1))
            )
        )
        """
        output = ()
        idx = 0
        for element in shape:
            if isinstance(element, int):
                for _ in range(element):
                    subscript = _subscript + (idx, )
                    idx += 1
                    output += (CallNodeSubscript(self, subscript), )
            elif isinstance(element, tuple):
                subscript = _subscript + (idx, )
                idx += 1
                output += (self.unpack(shape=element, _subscript=subscript), )
            elif isinstance(element, type(Ellipsis)):
                subscript = _subscript + (idx, )
                idx += 1
                output += (CallNodeSubscript(self, subscript), )
            else:
                raise TypeError("Invalid content in shape tuple")
        return output


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
            self.call, self.subscript
        )
