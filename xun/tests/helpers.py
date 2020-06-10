from collections import namedtuple
from io import StringIO
from pathlib import Path
from pyshd import pushd
import os
import pytest  # noqa: F401
import sys


class capture_stdout(StringIO):
    def __init__(self):
        super(capture_stdout, self).__init__()

    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self
        return self

    def __exit__(self, *args):
        sys.stdout = self._stdout
        self.seek(0)


tmpwd_paths = namedtuple('tmpwd_paths', ['old', 'new'])


@pytest.fixture()
def tmpwd(tmp_path):
    """
    work in a temporary directory
    """
    old = os.getcwd()
    with pushd(tmp_path):
        yield tmpwd_paths(Path(old), tmp_path)
