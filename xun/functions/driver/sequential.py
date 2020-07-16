from .. import CallNode, SentinelNode
from .driver import Driver
import networkx as nx


class Sequential(Driver):
    def load_from_store(self, program, sentinel):
        return program.store[sentinel.call]

    def run_and_store(self, program, call):
        func = program[call.function_name].compile()
        args = [
            self.load_from_store(program, arg)
            if isinstance(arg, SentinelNode) else arg
            for arg in call.args
        ]
        kwargs = {
            key: self.load_from_store(program, value)
            if isinstance(value, SentinelNode) else value
            for key, value in call.kwargs.items()
        }
        result = func(*args, **kwargs)

        program.store[CallNode(call.function_name, *args, **kwargs)] = result

    def exec(self, program):
        assert nx.is_directed_acyclic_graph(program.graph)

        schedule = nx.topological_sort(program.graph)

        for task in schedule:
            if not isinstance(task, CallNode):
                continue
            self.run_and_store(program, task)

        return program.store[program.entry_call]
