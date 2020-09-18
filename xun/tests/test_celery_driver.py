from .helpers import PicklableMemoryStore
from xun.functions import CallNode
import gc
import threading
import time
import xun


def test_celery_driver(xun_celery_worker):
    from .reference import decending_fibonacci

    with PicklableMemoryStore() as store:
        blueprint = decending_fibonacci.blueprint(6)
        result = blueprint.run(
            driver=xun.functions.driver.Celery(broker_url='memory://'),
            store=store,
        )

    expected = [5, 3, 2, 1, 1, 0]
    assert result == expected


# Locks and other concurrency primitives cannot be pickled, so we cheat by
# wrapping them in a non shared function
events = {}
def get_event(name):
    return events.setdefault(name, threading.Event())


def test_celery_concurrency(xun_celery_worker):
    # For tests celery will run with a single worker, but since the celery
    # driver is asyncronous, we indirectly inspect the order of work to ensure
    # concurrency.

    # The following configuration should result in a schedule of the following
    # form:
    #
    #   a
    #  / \
    # b   c
    #  \ /
    #   d
    #
    # The should should therefore be populated in this order:
    # 0: [a]
    # 1: [b, c]
    # 0: [d]

    @xun.function()
    def a():
        get_event('started').set()
        get_event('1st').wait(timeout=10.0)

    @xun.function()
    def b():
        get_event('2nd').wait(timeout=10.0)
        with ...:
            a()

    @xun.function()
    def c():
        get_event('2nd').wait(timeout=10.0)
        with ...:
            a()

    @xun.function()
    def d():
        msg = "The body cannot yet be empty"
        with ...:
            b()
            c()

    started_event = get_event('started')
    first_event = get_event('1st')
    second_event = get_event('2nd')

    workflow_error = None
    def workflow():
        try:
            with PicklableMemoryStore() as store:
                result = d.blueprint().run(
                    driver=xun.functions.driver.Celery(broker_url='memory://'),
                    store=store,
                )
        except Exception as e:
            workflow_error = e
    workflow_thread = threading.Thread(target=workflow)
    workflow_thread.start()

    # Wait for the workflow to begin
    assert started_event.wait(timeout=10.0)

    # Capture the internal state of the driver
    acs = None
    for obj in gc.get_objects():
        if isinstance(
                obj,
                xun.functions.driver.celery.AsyncCeleryState,
            ) and obj.visited == {
                # There might be more than one state object alive, so we need
                # to identify ours
                CallNode('a')
            }:
            acs = obj

    assert acs is not None

    # This will let the a task complete, so that b and c can be schduled
    first_event.set()

    # If the b _and_ c are visited, the program is concurrent.
    waited = 0.0
    while acs.visited != {
            CallNode('a'),
            CallNode('b'),
            CallNode('c'),
        } and waited < 10.0:
        time.sleep(0.01)
        waited += 0.01

    # d should be the only node left unvisited
    assert acs.visited == {
            CallNode('a'),
            CallNode('b'),
            CallNode('c'),
        }

    # Let b and c complete, d should then finish
    second_event.set()

    workflow_thread.join()
