from .helpers import PicklableMemoryStore
from .helpers import sample_sin_blueprint
from dask.distributed import Client
from contextlib import closing
import xun


def test_dask_driver():
    client = Client(processes=False)
    dask_driver = xun.functions.driver.Dask(client)

    blueprint, expected = sample_sin_blueprint()

    with closing(client):
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
