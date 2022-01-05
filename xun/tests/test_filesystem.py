from base64 import urlsafe_b64encode
from xun.fs.filesystem import wait_for_ctrl
import contextlib
import os
import pickle
import pytest
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
def simple_store():
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

        callnodes = sorted(callnode.sha256() for callnode in store_contents)
        yield mnt_pnt, store, callnodes, f


def test_filesystem():
    with tempfile.TemporaryDirectory() as tmp, xun.fs.mount(store, query, tmp):
        assert tree(tmp) == expected


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
        print(cmd)
        proc = subprocess.Popen(cmd)
        timeout = 5
        try:
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


def test_filesystem_control_refresh():
    with simple_store() as (mnt_pnt, _, callnodes, f):
        def ls():
            return sorted(os.listdir(os.path.join(mnt_pnt, 'store')))
        assert ls() == callnodes

        new = f.callnode('d')
        store.store(new, 'hello', tag='tag')
        assert ls() == callnodes

        refresh = os.path.abspath(os.path.join(mnt_pnt, 'refresh'))
        subprocess.check_call(refresh)
        assert ls() == sorted(callnodes + [new.sha256()])


def test_delete_mounted_deletes_store():
    with simple_store() as (mnt_pnt, store, callnodes, f):
        a = callnodes[0]

        assert a in store
        file = Path(mnt_pnt) / 'store' / a.sha256()
        file.unlink()
        assert a not in store


def test_read_tags():
    with tempfile.TemporaryDirectory() as tmp, xun.fs.mount(store, query,
                                                            tmp) as mnt:
        assert store.tags(a) == {
            'entry_call': 'main-1dfvqooTGxQ6QWEJInEAEpP03d_e4rJLrE1GZmsCYL4=',
            'errored': 'false',
            'function': 'f-0ZrVn3HSuj3hggTOtnC6QaOWyo7IHTRsMLc4FPypXbY=',
            'hash': '6zwGDQf9J4iAj3q_kSwKnyD2ewHJ86d0GzwKILGbfXY=',
            'readers': ':john_117:installation_04:',
            'start_time': '2030-01-01T00:00:00+00:00',
            'username': 'guilty_spark',
        }
        file = mnt / a.hash()

        with file.open() as f:

            def is_tag(s):
                return s.startswith('tag ')

            lns = sorted(filter(is_tag, f.readlines()))

        tags = [
            'tag entry_call main-1dfvqooTGxQ6QWEJInEAEpP03d_e4rJLrE1GZmsCYL4=',
            'tag errored false',
            'tag function f-0ZrVn3HSuj3hggTOtnC6QaOWyo7IHTRsMLc4FPypXbY=',
            'tag hash 6zwGDQf9J4iAj3q_kSwKnyD2ewHJ86d0GzwKILGbfXY=',
            'tag start_time 2030-01-01T00:00:00+00:00',
            'tag username guilty_spark',
        ]

        assert all(tag in lns for tag in tags)


def test_write_tags():
    with tempfile.TemporaryDirectory() as tmp, xun.fs.mount(store, query,
                                                            tmp) as mnt:
        file = mnt / a.hash()

        with file.open('w') as f:
            print('tag custom_tag hello world', file=f)

        assert 'custom_tag' in store.tags(a)
        assert store.tags(a)['custom_tag'] == 'hello world'
