import os
import tempfile
import xun

store = xun.functions.store.Disk('xun/tests/test_data/xun-fs-store')
query = """
(start_time>="2030-01-02" entry_point function_name) =>
    date(start_time) {
        entry_point {
            function_name {
                ...
            }
        }
    }
"""


def tree(path):
    return sorted(
        os.path.relpath(os.path.join(dir, file), start=path)
        for dir, _, files in os.walk(path) for file in files)


def test_filesystem():
    with tempfile.TemporaryDirectory() as tmp, xun.fs.mount(store, query, tmp):
        assert tree(tmp) == sorted([
            '2030-01-01/main/f/79d963e6',
            '2030-01-01/main/f/aa8cad74',
            '2030-01-01/main/g/05fd3d1f',
            '2030-01-01/main/main/bc7bad12'
            '2030-12-01/main/g/fa7cb530',
            '2030-12-01/main/main/828afbec',
        ])


def test_filesystem_cli():
    with tempfile.TemporaryDirectory() as tmp:
        cmd = f'xun mount -s disk -p xun/tests/test_data/xun-fs-store {tmp}'
        assert tree(tmp) == sorted([
            '2030-01-01/main/f/79d963e6',
            '2030-01-01/main/f/aa8cad74',
            '2030-01-01/main/g/05fd3d1f',
            '2030-01-01/main/main/bc7bad12'
            '2030-12-01/main/g/fa7cb530',
            '2030-12-01/main/main/828afbec',
        ])


def test_delete_mounted_deletes_store():
    with tempfile.TemporaryDirectory() as tmp, xun.fs.mount(store, query,
                                                            tmp) as mnt:
        assert a in store
        file = mnt / a.hash()
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
