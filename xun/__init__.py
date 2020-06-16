try:
    import pkg_resources
    __version__ = pkg_resources.get_distribution(__name__).version
except pkg_resources.DistributionNotFound:
    pass


from .core import ExtractError


from . import sima


__all__ = [
    'ExtractError',

    'sima',
]
