from .test_stores import TmpDisk
from .test_stores import create_instance
from base64 import urlsafe_b64encode
import contextlib
import os
import pickle
import pytest
import shutil
import subprocess
import tempfile
import xun


store = xun.functions.store.Disk('xun/tests/test_data/xun-fs-store')
query = """
(start_time>="2030-01-02" entry_point function_name) =>
    start_time {
        entry_point {
            function_name {
                ...
            }
        }
    }
"""
expected = sorted([
    ('control', 0o100200),
    ('refresh', 0o100500),
    ('store/2030-01-02T13:37:00+00:00/main/f/'
     'i-61R9ZvhrLqMJTd5uI__mIctKDd0B8lhcnGuEK46wg=', 0o100600),
    ('store/2030-01-02T13:37:00+00:00/main/f/'
     'mrasCwYq-xgxF31_sLzWoFC-nityLw-B5mxymJHqcM4=', 0o100600),
    ('store/2030-01-02T13:37:00+00:00/main/main/'
     'KtKWyz-WXKQN5JqoXxcoJ_rdt4L3z7LFsceotmVd8MM=', 0o100600),
    ('store/2030-01-03T13:37:00+00:00/main/f/'
     'FyhmbEKFuHsxAssR-gdIhx5mAljsKg0LotLBuRrZnng=', 0o100600),
    ('store/2030-01-03T13:37:00+00:00/main/main/'
     'uJVEipdbWNDxXvSsmtVtKt6dn6PS2YLK8ppLoEcdefc=', 0o100600),
])


def tree(path):
    files = sorted(
        os.path.relpath(os.path.join(dir, file), start=path)
        for dir, _, files in os.walk(path) for file in files)
    return [(f, os.stat(os.path.join(path, f)).st_mode) for f in files]


@contextlib.contextmanager
def simple_store_mnt():
    @xun.function()
    def f(*args, **kwargs):
        return args, kwargs

    store_contents = {
        f.callnode('a'): ('hello', {'tag': 'tag'}),
        f.callnode('b'): ('world', {'tag': 'tag'}),
        f.callnode('c'): ('goodbye', {'tag': 'tag'}),
    }

    with contextlib.ExitStack() as stack:
        tmp = stack.enter_context(tempfile.TemporaryDirectory())

        store = xun.functions.store.Disk(os.path.join(tmp, 'store'))
        for callnode, (value, tags) in store_contents.items():
            store.store(callnode, value, **tags)

        mnt_pnt = os.path.join(tmp, 'mnt')
        mnt_store = os.path.join(mnt_pnt, 'store')
        os.mkdir(mnt_pnt)
        stack.enter_context(
            xun.fs.mount(store, '() => ...', mnt_pnt, capture_output=False)
        )

        callnodes = [callnode for callnode in store_contents]
        yield mnt_pnt, store, callnodes, f


@pytest.mark.skipif(not xun.fs.fuse_available, reason='Fuse not available')
def test_filesystem():
    with tempfile.TemporaryDirectory() as tmp, xun.fs.mount(store, query, tmp):
        assert tree(tmp) == expected


@pytest.mark.skipif(not xun.fs.fuse_available, reason='Fuse not available')
@pytest.mark.parametrize('cmd', [
    ['python3', '-m', 'xun', 'mount', *store_args, *query_args]
    for store_args in [
        ['-s', 'disk', 'xun/tests/test_data/xun-fs-store'],
        ['--store', 'disk', 'xun/tests/test_data/xun-fs-store'],
        ['--store-pickle', urlsafe_b64encode(pickle.dumps(store)).decode()],
    ]
    for query_args in [
        ['-q', query],
        ['--query', query],
        ['--query-file', 'xun/tests/test_data/query.xunql'],
    ]
])
def test_filesystem_cli(cmd):
    with tempfile.TemporaryDirectory() as tmp:
        cmd += ['--', tmp]
        proc = subprocess.Popen(cmd)
        timeout = 5
        try:
            from xun.fs.filesystem import wait_for_ctrl
            wait_for_ctrl(tmp, timeout=timeout)
        except TimeoutError:
            msg = f'control file not mounted after {timeout} seconds'
            raise RuntimeError(msg)
        finally:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.mark.skipif(not xun.fs.fuse_available, reason='Fuse not available')
def test_filesystem_control_refresh():
    with simple_store_mnt() as (mnt_pnt, store, callnodes, f):
        hashes = sorted(callnode.sha256() for callnode in callnodes)
        def ls():
            return sorted(os.listdir(os.path.join(mnt_pnt, 'store')))
        assert ls() == hashes

        new = f.callnode('d')
        store.store(new, 'hello', tag='tag')
        assert ls() == hashes

        refresh = os.path.abspath(os.path.join(mnt_pnt, 'refresh'))
        subprocess.check_call(refresh)
        assert ls() == sorted(hashes + [new.sha256()])


@pytest.mark.skipif(not xun.fs.fuse_available, reason='Fuse not available')
def test_delete_mounted_deletes_store():
    with simple_store_mnt() as (mnt_pnt, store, callnodes, f):
        a = callnodes[0]

        assert a in store
        os.unlink(os.path.join(mnt_pnt, 'store', a.sha256()))
        assert a not in store


@pytest.mark.skipif(not xun.fs.fuse_available, reason='Fuse not available')
def test_rmdir_deletes_store_items():
    with contextlib.ExitStack() as exit_stack:
        mnt_pnt = exit_stack.enter_context(tempfile.TemporaryDirectory())
        (store, callnodes) = exit_stack.enter_context(create_instance(TmpDisk))
        exit_stack.enter_context(
            xun.fs.mount(store, query, mnt_pnt, capture_output=False)
        )

        path = os.path.join(
            mnt_pnt,
            'store',
            '2030-01-02T13:37:00+00:00',
        )
        assert callnodes.f_0 in store
        assert callnodes.f_1 in store
        assert callnodes.main_0 in store
        shutil.rmtree(path)
        assert not os.path.exists(path)
        assert callnodes.f_0 not in store
        assert callnodes.f_1 not in store
        assert callnodes.main_0 not in store
