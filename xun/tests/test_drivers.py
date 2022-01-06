from .helpers import PicklableMemoryStore
from .helpers import sample_sin_blueprint
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from dask.distributed import Client, LocalCluster
from contextlib import closing
from concurrent.futures import Future
from unittest.mock import patch
import dask
import pytest
import xun


def test_grpc_driver():
    blueprint, expected = sample_sin_blueprint()

    with PicklableMemoryStore() as store, ThreadPoolExecutor() as executor:
        server = xun.functions.driver.grpc.Server('localhost')
        driver = xun.functions.driver.grpc.Driver('localhost')
        server_future = executor.submit(server.start)
        futures = [
            executor.submit(blueprint.run, driver=driver, store=store)
            for _ in range(5)
        ]
        server_future.result(timeout=2.0)
        results = [f.result(timeout=1.5) for f in as_completed(futures)]

    assert result == expected


def test_dask_driver():
    client = Client(processes=False)
    dask_driver = xun.functions.driver.Dask(client)

    with closing(client):
        blueprint, expected = sample_sin_blueprint()

        with PicklableMemoryStore() as store:
            result = blueprint.run(driver=dask_driver, store=store)

    assert result == expected


def test_dask_driver_graph_intactibility():
    blueprint, expected = sample_sin_blueprint()

    nodes_before = list(blueprint.graph.nodes())
    edges_before = list(blueprint.graph.edges())

    client = Client(processes=False)
    dask_driver = xun.functions.driver.Dask(client)
    with closing(client):
        with PicklableMemoryStore() as store:
            result = blueprint.run(driver=dask_driver, store=store)
            nodes_after = list(blueprint.graph.nodes())
            edges_after = list(blueprint.graph.edges())

    assert nodes_before == nodes_after
    assert edges_after == edges_after


def test_seq_driver_graph_intactibility():
    blueprint, expected = sample_sin_blueprint()
    nodes_before = list(blueprint.graph.nodes())
    edges_before = list(blueprint.graph.edges())
    seq_driver = xun.functions.driver.Sequential()
    with PicklableMemoryStore() as store:
        result = blueprint.run(driver=seq_driver, store=store)
        nodes_after = list(blueprint.graph.nodes())
        edges_after = list(blueprint.graph.edges())

    assert nodes_before == nodes_after
    assert edges_after == edges_after


def test_dask_driver_tackles_simple_worker_resource():
    @xun.worker_resource('MEMORY', 10e2)
    @xun.function()
    def ftest():
        return 'test'

    cluster = LocalCluster(
        resources={'MEMORY': 10e2},
        processes=False,
        n_workers=1)
    client = Client(cluster)
    dask_driver = xun.functions.driver.Dask(client)

    with closing(client):
        blueprint = ftest.blueprint()
        with PicklableMemoryStore() as store:
            result = blueprint.run(driver=dask_driver, store=store)

    cluster.close()

    assert result == 'test'


def test_dask_driver_config_worker_resource():
    @xun.worker_resource('MEMORY', 10e2)
    @xun.function()
    def ftest():
        return 'test'

    # config must be set before the cluster is created
    with dask.config.set({"distributed.worker.resources.MEMORY": 10e2}):
        cluster = LocalCluster(processes=False, n_workers=1)
        client = Client(cluster)
        dask_driver = xun.functions.driver.Dask(client)
        with closing(client):
            blueprint = ftest.blueprint()
            with PicklableMemoryStore() as store:
                result = blueprint.run(driver=dask_driver, store=store)

        cluster.close()

    assert result == 'test'


def test_dask_driver_adheres_to_worker_resources():
    @xun.worker_resource('MEMORY', 70e6)
    @xun.worker_resource('GPU', 2)
    @xun.function()
    def ftest():
        return 'test'

    client = Client(processes=False, n_workers=1)
    dask_driver = xun.functions.driver.Dask(client)

    blueprint = ftest.blueprint()

    future = Future()
    future.set_result(None)

    with closing(client):
        with patch("dask.distributed.Client.submit") as submit_mock:
            submit_mock.return_value = future
            with PicklableMemoryStore() as store:
                try:
                    blueprint.run(driver=dask_driver, store=store)
                except KeyError:
                    # KeyError is ok, since "run" should modify the store,
                    # but mock does not, and thus KeyError with occur
                    pass
    # python version <= 3.7 the following call unpacks to two items
    # python version >= 3.8 the following call unpacks to three items
    *_, submitmock_kwargs = submit_mock.call_args_list[0]
    # submit_mock.mock_calls[0].kwargs['resources']
    assert 'resources' in submitmock_kwargs
    assert submitmock_kwargs['resources'] == {
        'MEMORY': 70e6,
        'GPU': 2,
    }


@pytest.mark.parametrize('driver', [
    xun.functions.driver.Dask(Client(processes=False, n_workers=1)),
    xun.functions.driver.Sequential(),
])
def test_dask_global_resources(driver):
    @xun.global_resource('A', 1, default_available=2)
    @xun.global_resource('B', 2, default_available=2)
    @xun.function()
    def ftest():
        return 'test'

    with PicklableMemoryStore() as store:
        assert ftest.blueprint().run(driver=driver, store=store) == 'test'
