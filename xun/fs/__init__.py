from . import queries

try:
    from .filesystem import mount
except NotImplementedError:
    pass
else:
    from . import cli
