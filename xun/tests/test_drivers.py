from .helpers import PicklableMemoryStore
from .helpers import sample_sin_blueprint
from dask.distributed import Client, LocalCluster
from contextlib import closing
from concurrent.futures import Future
from unittest.mock import patch

import dask
import xun


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
