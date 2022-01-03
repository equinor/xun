import xun


def test_worker_resources():
    @xun.worker_resource("res", 3)
    @xun.worker_resource("GPU", 2)
    @xun.function()
    def f():
        pass
    assert f.worker_resources["res"] == 3
    assert f.worker_resources["GPU"] == 2


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
