from .helpers import PicklableMemoryStore
from .helpers import sample_sin_blueprint
from dask.distributed import Client
import xun


def test_dask_driver():
    client = Client(processes=False)
    dask_driver = xun.functions.driver.Dask(client)

    blueprint, expected = sample_sin_blueprint()

    with PicklableMemoryStore() as store:
        result = blueprint.run(driver=dask_driver, store=store)

    assert result == expected
    client.close()
