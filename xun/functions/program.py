from .functions import Function
from .functions import overwrite_globals
from . import transformations
import ast
import networkx as nx
import queue
import types


class Compiler:
    def __init__(self, context, entry_name):
        self.context = context
        self.entry_name = entry_name

    def compile(self, *args, **kwargs):
        call = CallNode(self.entry_name, *args, **kwargs)
        graph = build_call_graph(self.context, call)
        functions = build_functions(self.context)
        return Program(
            self.context.driver,
            self.context.store,
            graph,
            functions,
            call
        )


class Program:
    def __init__(self, driver, store, graph, functions, entry_call):
        self.driver = driver
        self.store = store
        self.graph = graph
        self.functions = functions
        self.entry_call = entry_call

    def __call__(self):
        return self.driver(self)

    def __getitem__(self, key):
        return self.functions.__dict__[key]



class CallNode:
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


class SentinelNode:
    def __init__(self, call):
        self.call = call

    def __copy__(self):
        raise _xun_CopyError('Cannot copy value')

    def __deepcopy__(self):
        raise _xun_CopyError('Cannot copy value')

    def __eq__(self, other):
        try:
            return self.call == other.call
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.call)

    def __repr__(self):
        return 'SentinelNode<{}>'.format(self.call)


class TargetNode:
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


class TargetNameNode:
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
        return 'TargetNameNode(target_name={})'.format(self.target_name)

    def to_target_node(self, owner):
        return TargetNode(self.target_name, owner)


def build_function_graph(context, call):
    def skip_xun_functions(node):
        return isinstance(node.func, ast.Name) and node.func.id in context

    decomposed = (Function(context[call.function_name].func)
        .apply(transformations.separate_constants)
        .apply(transformations.sort_constants)
        .apply(transformations.copy_only_constants,
               ignore_predicate=skip_xun_functions)
        .apply(transformations.build_xun_graph, context)
    )

    graph_builder = decomposed.compile(decomposed.xun_graph)
    graph = graph_builder(*call.args, **call.kwargs)

    # The compiled functions does not know it self, so it cannot return
    # TargetNodes. Instead, it returns TargetNameNodes, which need to be
    # converted
    graph = nx.relabel_nodes(
        graph,
        {
            t: t.to_target_node(call)
            for t in graph.nodes
            if isinstance(t, TargetNameNode)
        },
    )

    graph.add_edges_from((node, call) for node in sink_nodes(graph))

    if not nx.is_directed_acyclic_graph(graph):
        raise NotDAGError()

    dependencies = tuple(
        n for n in graph.nodes if isinstance(n, CallNode) and n != call
    )

    return graph, dependencies


def build_call_graph(context, call):
    graph, dependencies = build_function_graph(context, call)

    q = queue.Queue()
    visited = {call}

    for call in dependencies:
        q.put(call)

    while not q.empty():
        call = q.get()

        assert isinstance(call, CallNode)

        if call in visited:
            continue

        func_graph, dependencies = build_function_graph(context, call)

        for dependency in dependencies:
            q.put(dependency)

        graph = nx.compose(graph, func_graph)

        if not nx.is_directed_acyclic_graph(graph):
            raise NotDAGError()

    return graph


def sink_nodes(dag):
    if __debug__ and not nx.is_directed_acyclic_graph(dag):
        raise ValueError('dag must be directed acyclic graph')
    return [n for n, out_degree in dag.out_degree() if out_degree == 0]


def build_function(context, func):
    def skip_xun_functions(node):
        return isinstance(node.func, ast.Name) and node.func.id in context

    decomposed = (Function(func)
        .apply(transformations.separate_constants)
        .apply(transformations.sort_constants)
        .apply(transformations.copy_only_constants,
               ignore_predicate=skip_xun_functions)
        .apply(transformations.load_from_store, context)
    )

    func = decomposed.compile(decomposed.load_from_store, decomposed.body)
    globals_with_store = {
        **func.__globals__,
        '_xun_store': context.store
    }

    return overwrite_globals(func, globals_with_store)



def build_functions(context):
    functions = {}
    for fname, (desc, func) in context.functions.items():
        if fname in functions:
            raise ValueError('{} already exists'.format(fname))
        functions[fname] = build_function(context, func)
    return types.SimpleNamespace(**functions)
