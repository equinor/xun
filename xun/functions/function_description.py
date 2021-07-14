from .compatibility import ast
from .util import func_external_names
from .util import function_ast
from .util import function_source
from .util import strip_decorators
from collections import namedtuple
import inspect


FunctionDescription = namedtuple(
    'FunctionDescription',
    [
        'src',
        'ast',
        'name',
        'qualname',
        'doc',
        'annotations',
        'defaults',
        'globals',
        'referenced_modules',
        'module',
    ]
)


ModuleAlias = namedtuple(
    'ModuleAlias',
    [
        'module',
        'asname',
    ]
)


def describe(func):
    """ Describe function

    .. note:: Any function decorators will be removed

    Parameters
    ----------
    func : function
        Function to describe

    Returns
    -------
    FunctionDescription
        Description of the given function
    """
    src = function_source(func)
    tree = function_ast(func)

    is_single_function_module = (
        isinstance(tree, ast.Module)
        and len(tree.body) == 1
        and isinstance(tree.body[0], ast.FunctionDef)
    )

    if not is_single_function_module:
        raise ValueError('can only describe a single function')

    # Decorators can change the function in ways we don't control, unsupported.
    tree = strip_decorators(tree)

    # Find externally referenced names so that we only have to keep globals and
    # modules that are actually used.
    external_names = func_external_names(tree.body[0])

    external_references = {
        name: value
        for name, value in func.__globals__.items()
        if name in external_names
    }

    # Store function closure as globals
    def cell_is_empty(cell):
        try:
            cell.cell_contents
        except ValueError:
            return True
        return False
    if func.__closure__ is not None:
        external_references.update({
            name: cell.cell_contents
            for name, cell in zip(func.__code__.co_freevars, func.__closure__)
            if name in external_names and not cell_is_empty(cell)
        })

    function_globals = {
        name: value
        for name, value in external_references.items()
        if not inspect.ismodule(value)
    }

    function_modules = frozenset(
        ModuleAlias(module=value.__name__, asname=name)
        for name, value in external_references.items()
        if name in external_names
        and inspect.ismodule(value)
    )

    return FunctionDescription(
        src=src,
        ast=tree,
        name=func.__name__,
        qualname=func.__qualname__,
        doc=func.__doc__,
        annotations=func.__annotations__,
        defaults=func.__defaults__,
        globals=function_globals,
        referenced_modules=function_modules,
        module=func.__module__,
    )
