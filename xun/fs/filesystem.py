from . import cli
from pathlib import Path
from textwrap import dedent
import contextlib
import errno
import networkx as nx
import os
import stat
import subprocess


# fuse-py import magic
# ref: https://github.com/libfuse/python-fuse/blob/master/example/hello.py
# pull in some spaghetti to make this stuff work without fuse-py being installed
# try:
#     import _find_fuse_parts
# except ImportError:
#     pass
try:
    import fuse
    from fuse import Fuse
    if not hasattr(fuse, '__version__'):
        raise RuntimeError("your fuse-py doesn't know of fuse.__version__, probably it's too old.")
    fuse.fuse_python_api = (0, 2)
except ImportError:
    raise NotImplementedError('Missing fuse')


@contextlib.contextmanager
def mount(store, query, mountpoint):
    import pickle
    cmd = [
        'xun',
        'mount',
        '--store-pickle', pickle.dumps(store).hex(),
        '--query', query,
        '--',
        str(mountpoint)
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            # stdout=subprocess.PIPE,
            # stderr=subprocess.PIPE,
        )
        try:
            proc.wait(1)
        except subprocess.TimeoutExpired:
            pass
        else:
            out, err = proc.communicate()
            msg = dedent(f'''\
                xun mount stdout:
                {out.decode()}

                xun mount stderr:
                {err.decode()}
            ''')
            raise RuntimeError(f'failed to mount\n{msg}')
        yield Path(mountpoint)
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()


class XunFS(Fuse):
    class File:
        def __init__(self, path, mode=0):
            self.path = path
            self.mode = mode
            self.mode_mask = os.O_RDONLY | os.O_WRONLY | os.O_RDWR

        def open(self, flags):
            if self.mode and not (self.flags & self.mode_mask) == self.mode:
                return -errno.EACCES

        def read(self, size, offset):
            return -errno.EACCES

        def write(self, buf, offset):
            return -errno.EACCES

        def getattr(self):
            st = Stat()
            st.st_mode = stat.S_IFREG | self.mode
            st.st_nlink = 1
            return st

    class Refresh(File):
        def __init__(self, path):
            super().__init__(path, os.O_RDONLY)
            self.contents = dedent('''\
                #!/bin/bash
                echo refresh > `dirname $0`/control
            ''')

        def read(self, size, offset):
            length = len(self.contents)
            return self.contents[offset:offset + size]

    class Control(File):
        def __init__(self, path, fs):
            super().__init__(path, os.O_WRONLY)
            self.fs = fs
            self.commands = {
                'refresh', lambda *_: fs.refresh(),
            }

        def write(self, buf, offset):
            io = BytesIO(buf)
            actions = []
            lines = io.readlines()
            for ln in lines:
                ln = ln.strip
                if ln in self.commands:
                    actions.append(ln)
                else:
                    return -errno.EINVAL
            for action in actions:
                self.commands[action]()

    def __init__(self, store, query, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.store = store
        self.query = query

    @property
    def graph(self):
        try:
            return self._graph
        except AttributeError:
            self.refresh()
            return self._graph

    def refresh(self):
        graph = nx.DiGraph()

        graph.add_node('/control', file=self.Control('/control', self))
        graph.add_node('/refresh', file=self.Refresh('/refresh'))

        graph = self.add_path_edges('/control', graph)
        graph = self.add_path_edges('/refresh', graph)
        # graph = self.add_path_edges('/store', graph)

        # structure = self.store.query(self.query)
        # graph = self.add_structure_to_graph(structure, graph)

        self._graph = graph

    def getattr(self, path):
        print('getattr', path)
        if self.isdir(path):
            print('\tisdir', path)
            st = Stat()
            st.st_mode = stat.S_IFDIR | 0o700
            st.st_nlink = 1
            return st
        else:
            print('\tnotdir', path)
            return self.file(path).getattr()

    def open(self, path, flags):
        return -errno.EACCES

    def read(self, path, size, offset):
        graph = self.graph
        if path not in graph:
            return -errno.ENOENT
        return self.file(path).read(size, offset)

    def readdir(self, path, offset):
        graph = self.graph
        print(graph.edges())
        for node in graph.successors(path):
            yield fuse.Direntry(node)

    def readlink(self, path):
        raise NotImplementedError

    def rmdir(self, path):
        ...

    def unlink(self, path):
        ...

    def isdir(self, path):
        graph = self.graph
        return path in graph and 'file' not in graph.nodes[path]

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
    def add_structure_to_graph(structure, graph, prefix='/store'):
        graph = graph.copy()

        if isinstance(structure, dict):
            for name, children in structure.items():
                ...

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
