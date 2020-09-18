from collections import namedtuple
from pathlib import Path
from pyshd import pushd
import celery
import os
import pytest  # noqa: F401
import xun


tmpwd_paths = namedtuple('tmpwd_paths', ['old', 'new'])


@pytest.fixture()
def tmpwd(tmp_path):
    """
    work in a temporary directory
    """
    old = os.getcwd()
    with pushd(tmp_path):
        yield tmpwd_paths(Path(old), tmp_path)


@pytest.fixture()
def xun_celery_worker(request,
                      celery_worker_pool,
                      celery_worker_parameters):
    # type: (Any, Celery, Sequence[str], str, Any) -> WorkController
    """Fixture: Start worker in a thread, stop it when the test returns."""
    xun.functions.driver.celery.celery_app.conf.update(
        broker_url='memory://',
        result_backend='rpc://',
    )
    with celery.contrib.testing.worker.start_worker(
            xun.functions.driver.celery.celery_app,
            concurrency=2,
            pool=celery_worker_pool,
            **celery_worker_parameters) as w:
        yield w


@pytest.fixture(scope='session')
def celery_enable_logging():
    return True


@pytest.fixture
def celery_worker_parameters():
    # type: () -> Mapping[str, Any]
    """Redefine this fixture to change the init parameters of Celery workers.

    This can be used e. g. to define queues the worker will consume tasks from.

    The dict returned by your fixture will then be used
    as parameters when instantiating :class:`~celery.worker.WorkController`.
    """
    return {
        # For some reason this `celery.ping` is not registed IF our own worker is still
        # running. To avoid failing tests in that case, we disable the ping check.
        # see: https://github.com/celery/celery/issues/3642#issuecomment-369057682
        # here is the ping task: `from celery.contrib.testing.tasks import ping`
        'perform_ping_check': False,
    }
