from .util import func_external_names
from .util import function_ast
from .util import function_source
from .util import strip_decorators
from collections import namedtuple
import ast
import inspect


FunctionDescription = namedtuple(
    'FunctionDescription',
    [
        'src',
        'ast',
        'name',
        'defaults',
        'globals',
        'module_infos',
        'module',
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

    tree = strip_decorators(tree)

    # Keep only referenced globals
    external_references = func_external_names(tree.body[0])
    function_globals = {
        name: value
        for name, value in func.__globals__.items()
        if name in external_references
        and not inspect.ismodule(value)
    }

    # Store function closure as globals
    if func.__closure__ is not None:
        function_globals.update({
            name: cell.cell_contents
            for name, cell in zip(func.__code__.co_freevars, func.__closure__)
        })

    # Remember names of referenced modules
    module_infos = {
        name: value.__name__
        for name, value in func.__globals__.items()
        if name in external_references
        and inspect.ismodule(value)
    }

    return FunctionDescription(
        src=src,
        ast=tree,
        name=func.__name__,
        defaults=func.__defaults__,
        globals=function_globals,
        module_infos=module_infos,
        module=func.__module__,
    )
