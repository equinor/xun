import networkx as nx
from .errors import CopyError
from .errors import NotDAGError
from .util import make_hashable


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
    def __init__(self, function_name, function_hash, *args, **kwargs):
        self.function_name = function_name
        self.function_hash = function_hash
        self.subscript = ()
        self.args = make_hashable(args)
        self.kwargs = make_hashable(kwargs)

    def __getitem__(self, key):
        return self._replace(subscript=self.subscript + (key,))

    def __copy__(self):
        raise CopyError('Cannot copy value')

    def __deepcopy__(self, memo=None):
        raise CopyError('Cannot copy value')

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

    def unpack(self, shape, *, _subscript=()):
        """
        Unpack a CallNode into a tuple of CallNodes with a given shape using
        recursion.

        Examples
        --------
        >>> CallNode('f').unpack((2, (2,)))
        (
            CallNode('f', (0,)),
            CallNode('f', (1,)),
            (
                CallNode('f', (2, 0)),
                CallNode('f', (2, 1))
            )
        )
        """
        output = ()
        idx = 0
        for element in shape:
            if isinstance(element, int):
                for _ in range(element):
                    new_instance = self._replace(subscript=_subscript + (idx,))
                    output += (new_instance,)
                    idx += 1
            elif isinstance(element, tuple):
                subscript = _subscript + (idx,)
                idx += 1
                output += (self.unpack(shape=element, _subscript=subscript),)
            elif isinstance(element, type(Ellipsis)):
                new_instance = self._replace(subscript=_subscript + (idx,))
                output += (new_instance,)
                idx += 1
            else:
                raise TypeError("Invalid content in shape tuple")
        return output
