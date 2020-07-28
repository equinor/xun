from collections import namedtuple
from pathlib import Path
from pyshd import pushd
import os
import pytest  # noqa: F401


tmpwd_paths = namedtuple('tmpwd_paths', ['old', 'new'])


@pytest.fixture()
def tmpwd(tmp_path):
    """
    work in a temporary directory
    """
    old = os.getcwd()
    with pushd(tmp_path):
        yield tmpwd_paths(Path(old), tmp_path)
