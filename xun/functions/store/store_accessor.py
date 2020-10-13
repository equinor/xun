from .. import CallNode
from os import urandom
import networkx as nx


class StoreAccessor:
    def __init__(self, store):
        self.store = store

    def store_graph(self, graph, hash_for):
        def hashed_subgraph(graph, source):
            nodes = nx.algorithms.dag.descendants(graph, source)
            nodes.add(source)
            subgraph = graph.subgraph(nodes)
            return nx.relabel_nodes(subgraph, {
                node: (node, hash_for(node)) for node in subgraph.nodes()
            })

        for node in graph:
            subgraph = hashed_subgraph(graph, node)
            node_namespace = self.store / 'graphs' / node
            node_namespace[hash_for(node)] = subgraph

    def load_result(self, call, hash=None):
        namespace = self.store / 'results' / call
        hash = hash if hash is not None else namespace['latest']
        return namespace[hash]

    def store_result(self, call, hash, result):
        namespace = self.store / 'results' / call
        namespace[hash] = result
        namespace['latest'] = hash

    def completed(self, call, hash=None):
        namespace = self.store / 'results' / call
        hash = hash if hash is not None else namespace['latest']
        return hash in namespace

    def invalidate(self, call, hash=None):
        if not self.completed(call, hash):
            return

        namespace = self.store / 'results' / call
        hash = hash if hash is not None else namespace['latest']

        hash_bytes = bytes.fromhex(hash)
        noise = urandom(32)
        distorted = bytes(h ^ k for h, k in zip(hash_bytes, noise)).hex()

        namespace[distorted] = namespace.pop(hash)
        if namespace['latest'] == hash:
            namespace['latest'] = distorted

        call_graph = self.store / 'graphs' / call // hash
        for node, node_hash in call_graph.successors((call, hash)):
            self.invalidate(node, hash=node_hash)

    def resolve_call(self, call):
        """
        Given a call, replace any FutureValueNodes with values from the store.

        Parameters
        ----------
        call : CallNode

        Returns
        CallNode
            Call with FutureValueNodes replaced by the value they represent
        """
        args = [
            self.load_result(arg)
            if isinstance(arg, CallNode) else arg
            for arg in call.args
        ]
        kwargs = {
            key: self.load_result(value)
            if isinstance(value, CallNode) else value
            for key, value in call.kwargs.items()
        }
        return CallNode(call.function_name, *args, **kwargs)
