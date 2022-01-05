from . import cli
from io import BytesIO
from pathlib import Path
from textwrap import dedent
import contextlib
import errno
import networkx as nx
import os
import stat
import subprocess
import time


try:
    import fuse
    from fuse import Fuse
    if not hasattr(fuse, '__version__'):
        raise RuntimeError("your fuse-py doesn't know of fuse.__version__, probably it's too old.")
    fuse.fuse_python_api = (0, 2)
except ImportError:
    raise NotImplementedError('Missing fuse')


@contextlib.contextmanager
def mount(store, query, mountpoint, capture_output=True, timeout=5):
    import pickle
    import base64
    cmd = [
        'xun',
        'mount',
        '--store-pickle', base64.urlsafe_b64encode(pickle.dumps(store)),
        '--query', query,
        '--',
        str(mountpoint)
    ]
    try:
        kwargs = {} if not capture_output else {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
        }
        proc = subprocess.Popen(cmd, **kwargs)
        wait_for_ctrl(str(mountpoint), timeout=timeout)
        yield Path(mountpoint)
    except TimeoutError:
        if capture_output:
            out, err = proc.communicate()
            msg = dedent(f'''\
                xun mount stdout:
                {out.decode()}

                xun mount stderr:
                {err.decode()}
            ''')
            raise RuntimeError(f'failed to mount\n{msg}')
        else:
            raise RuntimeError('failed to mount')
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def wait_for_ctrl(path, timeout):
    interval = 0.1
    remaining = timeout
    ctrl_path = os.path.join(path, 'control')
    while True:
        time.sleep(interval)
        remaining -= interval

        if os.path.exists(ctrl_path):
            return

        if remaining <= 0:
            raise TimeoutError


class XunFS(Fuse):
    class File:
        def __init__(self, mode=0):
            self.mode = mode

        def open(self, flags):
            # accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
            # print(oct(flags), oct(self.mode_mask), oct(self.mode))
            # if self.mode and not (flags & self.mode_mask) == self.mode:
            #     return -errno.EACCES
            pass

        def read(self, size, offset):
            return -errno.EACCES

        def truncate(self, size):
            return -errno.EACCES

        def write(self, buf, offset):
            return -errno.EACCES

        def getattr(self):
            st = Stat()
            st.st_mode = stat.S_IFREG | self.mode
            st.st_nlink = 1
            return st

    class Refresh(File):
        def __init__(self):
            super().__init__(stat.S_IRUSR | stat.S_IXUSR)
            self.contents = dedent('''\
                #!/bin/bash
                echo refresh > `dirname $0`/control
            ''')

        def read(self, size, offset):
            # length = len(self.contents)
            return self.contents[offset:offset + size].encode()

        def getattr(self):
            st = Stat()
            st.st_mode = stat.S_IFREG | self.mode
            st.st_size = len(self.contents)
            st.st_nlink = 1
            return st

    class Control(File):
        def __init__(self, fs):
            super().__init__(stat.S_IWUSR)
            self.fs = fs
            self.commands = {
                b'refresh': lambda *_: fs.refresh(),
            }

        def truncate(self, size):
            pass

        def write(self, buf, offset):
            io = BytesIO(buf)
            actions = []
            lines = io.readlines()

            for ln in lines:
                ln = ln.strip()
                if ln in self.commands:
                    actions.append(ln)
                else:
                    return -errno.EINVAL
            for action in actions:
                self.commands[action]()

            return len(buf)

    def __init__(self, store, query, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        self.query = query
        self.refresh()

    def refresh(self):
        graph = nx.DiGraph()

        graph.add_node('/control', file=self.Control(self))
        graph.add_node('/refresh', file=self.Refresh())

        graph = self.add_path_edges('/control', graph)
        graph = self.add_path_edges('/refresh', graph)
        graph = self.add_path_edges('/store', graph)

        print('self.query', self.query)
        structure = self.store.query(self.query)
        print('structure', structure)
        graph = self.add_structure_to_graph(structure, graph)

        self.graph = graph

    def getattr(self, path):
        if self.is_file(path):
            return self.file(path).getattr()
        else:
            st = Stat()
            st.st_mode = stat.S_IFDIR | 0o500
            st.st_nlink = 1
            return st

    def open(self, path, flags):
        try:
            return self.graph.nodes[path]['file'].open(flags)
        except KeyError:
            return -errno.ENOENT

    def read(self, path, size, offset):
        graph = self.graph
        if path not in graph:
            return -errno.ENOENT
        return self.file(path).read(size, offset)

    def readdir(self, path, offset):
        graph = self.graph
        for node in graph.successors(path):
            yield fuse.Direntry(os.path.basename(node))

    def readlink(self, path):
        raise RuntimeError

    def rmdir(self, path):
        raise RuntimeError

    def truncate(self, path, size):
        if self.is_file(path):
            return self.file(path).truncate(size)
        return -errno.EINVAL

    def unlink(self, path):
        raise RuntimeError

    def write(self, path, buf, offset):
        print(path, buf, offset)
        if self.is_file(path):
            return self.file(path).write(buf, offset)
        return -errno.EINVAL

    def is_file(self, path):
        return path in self.graph and 'file' in self.graph.nodes[path]

    def file(self, path):
        return self.graph.nodes[path]['file']

    @staticmethod
    def add_path_edges(path, graph):
        graph = graph.copy()
        parent, _ = os.path.split(path)
        while parent and parent != '/':
            graph.add_edge(parent, path)
            path = parent
            parent, _ = os.path.split(path)
        graph.add_edge('/', path)
        return graph

    @staticmethod
    def add_structure_to_graph(structure, graph, prefix='/store', copy=True):
        if copy:
            graph = graph.copy()

        if isinstance(structure, dict):
            for name, children in structure.items():
                name = os.path.join(prefix, name)
                graph.add_edge(prefix, name)
                graph = XunFS.add_structure_to_graph(
                    children,
                     graph,
                     prefix=name,
                     copy=False,
                 )
        else:
            for callnode in structure:
                name = os.path.join(prefix, callnode.sha256())
                graph.add_node(name, file=XunFS.File(0o600))
                graph.add_edge(prefix, name)

        return graph


class Stat(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0
