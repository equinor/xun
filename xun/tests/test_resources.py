from .helpers import run_in_process
import xun
import pytest


def test_worker_resources():
    @xun.worker_resource('res', 3)
    @xun.worker_resource('GPU', 2)
    @xun.function()
    def f():
        pass
    assert f.worker_resources['res'] == 3
    assert f.worker_resources['GPU'] == 2


def test_override_worker_resources():
    @xun.worker_resource('res', 3)
    @xun.worker_resource('GPU', 2)
    @xun.function()
    def f():
        pass
    g = xun.worker_resource('GPU', 1)(f)
    assert f.worker_resources['GPU'] == 2 and f.worker_resources['res'] == 3
    assert g.worker_resources['GPU'] == 1 and g.worker_resources['res'] == 3
    assert g.desc.src == f.desc.src


def test_global_resources():
    @xun.global_resource('zephyre', 2, default_available=1)
    @xun.function()
    def download():
        return 'content'

    assert download.global_resources['zephyre'] == (2, 1)

    with pytest.raises(xun.InsufficientResourceError):
        run_in_process(download.blueprint())

    assert run_in_process(download.blueprint(),
                          global_resources={'zephyre': 2})


def test_override_global_resources():
    @xun.global_resource('another', 3, default_available=4)
    @xun.global_resource('zephyre', 2, default_available=4)
    @xun.function()
    def f():
        pass

    g = xun.global_resource('zephyre', 1, default_available=4)(f)

    assert f.global_resources['zephyre'] == (2, 4)
    assert f.global_resources['another'] == (3, 4)

    assert g.global_resources['zephyre'] == (1, 4)
    assert g.global_resources['another'] == (3, 4)

    assert g.desc.src == f.desc.src


def test_error_on_resource_default_conflict():
    @xun.global_resource('resource_a', 1, default_available=1)
    @xun.function()
    def f():
        pass

    @xun.global_resource('resource_a', 1, default_available=2)
    @xun.function()
    def g():
        return 'ok'
        with ...:
            f()

    with pytest.raises(xun.ResourceConflictError):
        run_in_process(g.blueprint())

    assert run_in_process(
        g.blueprint(),
        global_resources={'resource_a': 3},
    ) == 'ok'


def test_resources_does_not_change_function_hash():
    @xun.global_resource('r', 1, default_available=2)
    @xun.function()
    def f():
        return 'hello world'

    hash0 = f.sha256()

    @xun.global_resource('r', 2, default_available=3)
    @xun.function()
    def f():
        return 'hello world'

    hash1 = f.sha256()

    assert hash0 == hash1
