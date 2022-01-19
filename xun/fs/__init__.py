from . import queries

try:
    from .filesystem import mount
except NotImplementedError:
    pass
    fuse_available = False
else:
    from . import cli
    fuse_available = True
