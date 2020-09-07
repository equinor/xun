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
            tuple(self.kwargs.items())
        ))

    def __repr__(self):
        args = []
        if len(self.args) > 0:
            args.append(', '.join(repr(a) for a in self.args))
        if len(self.kwargs) > 0:
            args.append(', '.join(
                '{}={}'.format(k, v) for k, v in self.kwargs.items()
            ))
        return 'CallNode<{}({})>'.format(self.function_name, ', '.join(args))


class FutureValueNode:
    """FutureValueNode

    This node serves two purposes, they are used as sentinel nodes representing
    future values in the call graph. And are used as guards when building the
    call graph. When the call graph is built, the functions doing the building
    will use sentinel nodes as representations for values returned by context
    functions. This makes let's us use the FutureValueNodes nodes directly in the
    function dependency graph.

    Another use is that because FutureValueNode are not copyable, and arguments
    and results to and from calls to functions outside xun functions are copied,
    they cannot be used for anything other than as arguments to other xun
    functions. This guards against attempted changes to future values, something
    that is of course impossible.

    Attributes
    ----------
    call : CallNode
        The CallNode whose result this Node represents
    """
    def __init__(self, call):
        self.call = call

    def __copy__(self):
        raise CopyError('Cannot copy value')

    def __deepcopy__(self, memo=None):
        raise CopyError('Cannot copy value')

    def __eq__(self, other):
        try:
            return self.call == other.call
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.call)

    def __repr__(self):
        return 'FutureValueNode<{}>'.format(self.call)


class TargetNode:
    """TargetNode

    Targets are the results of assignments in with constant statements. Given
    the following client code::

        @xun.function()
        def job(future_node1, future_node2, some_argument):
            return some_computation(target2, target3, some_argument)
            with ...:
                target1 = some_context_function(future_node1)
                target2 = some_context_function(future_node2)
                target3 = some_other_context_function(target1)

    will produce the following call graph
    assuming
        call_node = CallNode<job(future_node1, future_node2, some_argument)>

    G
    |
    v
    * future_node1
    |
    * CallNode<some_context_function(future_node1)>
    |
    * TargetNode(name=target1, owner=call_node)
    |
    * CallNode<some_other_context_function(target1)>
    |
    * TargetNode(name=target3, owner=call_node)
    |
    | G
    | |
    | v
    | * future_node2
    | |
    | * CallNode<some_other_context_function(future_node2)
    | |
    | * TargetNode(name=target2, owner=call_node)
    |/
    * call_node
    |
    v
    G

    The graph execution is top to bottom, that is, in order to call call_node,
    target2 and target3 must be completed.


    Attributes
    ----------
    name : str
        name of the target
    other : CallNode
        The call owning this target
    """
    def __init__(self, name, owner):
        self.name = name
        self.owner = owner

    def __eq__(self, other):
        try:
            return self.name == other.name and self.owner == other.owner
        except AttributeError:
            return False

    def __hash__(self):
        return hash((self.name, self.owner))

    def __repr__(self):
        return 'TargetNode(name={}, owner={})'.format(self.name, self.owner)


class TargetNameOnlyNode:
    """TargetNameOnlyNode

    Temporary target node used before it is converted to a TargetNode. This
    node is only aware of its name, but not of its owner

    Attributes
    ----------
    target_name : str
        The name of the target this node represents

    See Also
    --------
    TargetNode
    """
    def __init__(self, name):
        self.target_name = name

    def __eq__(self, other):
        try:
            return self.target_name == other.target_name
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.target_name)

    def __repr__(self):
        return 'TargetNameOnlyNode(target_name={})'.format(self.target_name)

    def to_target_node(self, owner):
        """To target node

        Create a full TargetNode from this node

        Parameters
        ----------
        owner : CallNode
            The call node that owns the TargetNode

        Returns
        -------
        TargetNode
            The full TargetNode this TargetNameOnlyNode should become
        """
        return TargetNode(self.target_name, owner)
