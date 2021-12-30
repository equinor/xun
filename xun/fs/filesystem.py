from . import cli
from pathlib import Path
import contextlib
import subprocess


@contextlib.contextmanager
def mount(store, query, mountpoint):
    cmd = [
        'xun',
        'mount',
        '--store-pickle', pickle.dumps(store).hex(),
        '--query', query,
        '--',
        str(mountpoint)
    ]
    try:
        proc = subprocess.Popen(cmd)
        yield Path(mountpoint)
    finally:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
