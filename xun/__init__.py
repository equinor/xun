try:
    import pkg_resources
    __version__ = pkg_resources.get_distribution(__name__).version
except pkg_resources.DistributionNotFound:
    pass


from . import fs
from . import serialization
from .core import ExportError
from .core import SchemaError
from .core import args_hash
from .core import filename_from_args
from .functions import ComputeError
from .functions import CopyError
from .functions import Function
from .functions import FunctionDefNotFoundError
from .functions import FunctionError
from .functions import InsufficientResourceError
from .functions import NotDAGError
from .functions import ResourceConflictError
from .functions import XunSyntaxError
from .functions import describe
from .functions import function_ast
from .functions import function_source
from .functions import make_shared
from .init import init_notebook
from .memoized import memoized
from .serialization import Reference


# User facing API
from .functions import function
from .functions import global_resource
from .functions import worker_resource
