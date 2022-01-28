from .driver import Driver as XunDriver
from enum import Enum
import asyncio
import contextlib
import contextvars
import grpc
import pkg_resources


proto_source = pkg_resources.resource_filename(__name__, "grpc.proto")
protos, services = grpc.protos_and_services('xun/functions/driver/grpc.proto')


def grpc_callndoe_id(callnode):
    return protos.CallNode(callnode=callnode.sha256(encode=False))


class Driver(XunDriver):
    def __init__(self, addr):
        self.addr = addr
        self._ctx_graph = contextvars.ContextVar('_ctx_graph')
        self._ctx_func_imgs = contextvars.ContextVar('_ctx_func_imgs')
        self._ctx_store = contextvars.ContextVar('_ctx_store')
        self._ctx_grpc_stub = contextvars.ContextVar('_ctx_grpc_stub')

    def _exec(self, graph, entry_call, function_images, store):
        ctx = contextvars.copy_context()

        async def run_async():
            await asyncio.sleep(0.5)
            async with grpc.aio.insecure_channel('[::]:50051') as channel:
                stub = services.XunGRPCStub(channel)

                self._ctx_graph.set(graph)
                self._ctx_func_imgs.set(function_images)
                self._ctx_store.set(store)
                self._ctx_grpc_stub.set(stub)

                return await self.async_exec(entry_call)

        return ctx.run(asyncio.run, run_async())

    @property
    def graph(self):
        return self._ctx_graph.get()

    @property
    def function_images(self):
        return self._ctx_func_imgs.get()

    @property
    def store(self):
        return self._ctx_store.get()

    async def async_exec(self, node):
        print('Starting', node)
        # This n ^ 2 in complexity
        await asyncio.gather(*[self.wait_for(n) for n in self.graph.predecessors(node)])
        if await self.assign(node):
            try:
                func = self.function_images[node.function_name]['callable']
                self.compute_and_store(node, func, self.store)
            finally:
                await self.done(node)
        else:
            return await self.wait_for(node)

    async def assign(self, node):
        payload = grpc_callndoe_id(node)
        return (await self._ctx_grpc_stub.get().Assign(payload)).assigned

    async def done(self, node):
        payload = grpc_callndoe_id(node)
        await self._ctx_grpc_stub.get().Assign(payload)

    async def wait_for(self, node):
        payload = grpc_callndoe_id(node)
        status = await self._ctx_grpc_stub.get().Await(payload)
        raise NotImplementedError


class Server:
    class Service(services.XunGRPCServicer):
        class Status(Enum):
            COMPLETED = 0
            FAILED = 1

        def __init__(self):
            super().__init__()
            self.events = {}
            self.futures = {}

        async def register(self, callnode):
            self.events[callnode] = asyncio.Event()
            await self.events[callnode].wait()
            return self.futures[callnode]

        async def Assign(self, request, context):
            callnode = request.callnode
            if callnode in self.futures:
                return protos.Assignment(assigned=False)
            else:
                self.assigned[callnode] = self.register(callnode)
                return protos.Assignment(assigned=True)

        async def Await(self, request, context):
            status = await self.futures[request.callnode]
            return protos.Status(status=status.value)

        async def Done(self, request, context):
            self.events[request.callnode].set()
            return protos.Empty()

    def __init__(self, _):
        pass

    async def astart(self):
        server = grpc.aio.server()
        services.add_XunGRPCServicer_to_server(self.Service(), server)
        listen_addr = '[::]:50051'
        server.add_insecure_port(listen_addr)
        # logging.info("Starting server on %s", listen_addr)
        print("Starting server on %s", listen_addr)
        await server.start()
        await server.wait_for_termination()

    def start(self):
        asyncio.run(self.astart())
