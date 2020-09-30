# flake8: noqa
"""ast

This module is an attempt at backporting breaking 3.6 and 3.8 changes to older
Python versions.
"""


from collections import namedtuple as _namedtuple
import copy as _copy
import sys as _sys


_major_version = _sys.version_info[0]
_minor_version = _sys.version_info[1]


from ast import AST


def __uninstantiable__init__(self, *args, **kwargs):
    raise TypeError('Type {} not available'.format(type(self)))
__uninstantiable = {'__init__': __uninstantiable__init__}


from ast import Add
from ast import And
try:
    from ast import AnnAssign
except ImportError:
    AnnAssign = type('AnnAssign', (AST, ), __uninstantiable)
from ast import Assert
from ast import Assign
from ast import AsyncFor
from ast import AsyncFunctionDef
from ast import AsyncWith
from ast import Attribute
from ast import AugAssign
from ast import AugLoad
from ast import AugStore
from ast import Await
from ast import BinOp
from ast import BitAnd
from ast import BitOr
from ast import BitXor
from ast import BoolOp
from ast import Break
from ast import Bytes
from ast import Call
from ast import ClassDef
from ast import Compare
if _major_version >= 3 and _minor_version >= 8:
    from ast import Constant
else:
    def _constant():
        from ast import Num as _Num
        from ast import Str as _Str
        from ast import Bytes as _Bytes
        from ast import NameConstant as _NameConstant
        from ast import Ellipsis as _Ellipsis
        class _ConstantMeta(type):
            def __instancecheck__(cls, instance):
                return cls.__subclasscheck__(cls, type(instance))
            def __subclasscheck__(cls, other):
                return (
                    other is _Num or
                    other is _Str or
                    other is _Bytes or
                    other is _NameConstant or
                    other is _Ellipsis
                )
        class _Constant(_ConstantMeta, metaclass=_ConstantMeta):
            """ _Constant

            This class is defined using a metaclass. The reason for this is
            that the node class ast.Constant does not exist in older Python
            versions. However, the five node classes that exist instead of
            ast.Constant must still count as ast.Constant classes in instance
            checks.
            """
            def __new__(cls):
                return type.__new__(cls, 'Constants', (_ConstantMeta, ), {})
            def __init__(self):
                pass
            def __call__(self, value, kind=None):
                if isinstance(value, (bool, type(None))):
                    # bools are ints, so this should be checked first
                    return _NameConstant(value)
                elif isinstance(value, (int, float, complex)):
                    return _Num(value)
                elif isinstance(value, str):
                    return _Str(value)
                elif isinstance(value, bytes):
                    return _Bytes(value)
                elif isinstance(value, type(...)):
                    return _Ellipsis()
                else:
                    raise ValueError('Unknown constant type {}'.format(value))
        return _Constant()
    Constant = _constant()
from ast import Continue
from ast import Del
from ast import Delete
from ast import Dict
from ast import DictComp
from ast import Div
from ast import Ellipsis
from ast import Eq
from ast import ExceptHandler
from ast import Expr
from ast import Expression
from ast import ExtSlice
from ast import FloorDiv
from ast import For
try:
    from ast import FormattedValue
except ImportError:
    FormattedValue = type('FormattedValue', (AST, ), __uninstantiable)
from ast import FunctionDef
try:
    from ast import FunctionType
except ImportError:
    FunctionType = type('FunctionType', (AST, ), __uninstantiable)
from ast import GeneratorExp
from ast import Global
from ast import Gt
from ast import GtE
from ast import If
from ast import IfExp
from ast import Import
from ast import ImportFrom
from ast import In
from ast import Index
from ast import Interactive
from ast import Invert
from ast import Is
from ast import IsNot
try:
    from ast import JoinedStr
except ImportError:
    JoinedStr = type('JoinedStr', (AST, ), __uninstantiable)
from ast import LShift
from ast import Lambda
from ast import List
from ast import ListComp
from ast import Load
from ast import Lt
from ast import LtE
from ast import MatMult
from ast import Mod
from ast import Module
from ast import Mult
from ast import Name
from ast import NameConstant
try:
    from ast import NamedExpr
except ImportError:
    NamedExpr = type('NamedExpr', (AST, ), __uninstantiable)
from ast import NodeTransformer
from ast import NodeVisitor
from ast import Nonlocal
from ast import Not
from ast import NotEq
from ast import NotIn
from ast import Num
from ast import Or
from ast import Param
from ast import Pass
from ast import Pow
try:
    from ast import PyCF_ALLOW_TOP_LEVEL_AWAIT
except ImportError:
    PyCF_ALLOW_TOP_LEVEL_AWAIT = 8192
from ast import PyCF_ONLY_AST
try:
    from ast import PyCF_TYPE_COMMENTS
except ImportError:
    PyCF_TYPE_COMMENTS = 4096
from ast import RShift
from ast import Raise
from ast import Return
from ast import Set
from ast import SetComp
from ast import Slice
from ast import Starred
from ast import Store
from ast import Str
from ast import Sub
from ast import Subscript
from ast import Suite
from ast import Try
from ast import Tuple
try:
    from ast import TypeIgnore
except ImportError:
    TypeIgnore = _namedtuple(
        'TypeIgnore',
        [
            'lineno',
            'tag',
        ],
    )
from ast import UAdd
from ast import USub
from ast import UnaryOp
from ast import While
from ast import With
from ast import Yield
from ast import YieldFrom
from ast import alias
from ast import arg
from ast import arguments
from ast import boolop
from ast import cmpop
from ast import comprehension
from ast import copy_location
from ast import dump
from ast import excepthandler
from ast import expr
from ast import expr_context
from ast import fix_missing_locations
from ast import get_docstring
try:
    from ast import get_source_segment
except ImportError:
    # Referenced from Python 3.8 source code
    # https://github.com/python/cpython/blob/3.8/Lib/ast.py
    #
    # end_lineno and end_col_offset will always be missing in Python versions
    # before 3.8
    def get_source_segment(source, node, *, padded=False):
        """Get source code segment of the *source* that generated *node*.
        If some location information (`lineno`, `end_lineno`, `col_offset`,
        or `end_col_offset`) is missing, return None.
        If *padded* is `True`, the first line of a multi-line statement will
        be padded with spaces to match its original position.
        """
        return None
from ast import increment_lineno
from ast import iter_child_nodes
from ast import iter_fields
from ast import keyword
from ast import literal_eval
from ast import mod
from ast import operator
if _major_version >= 3 and _minor_version >= 8:
    from ast import parse
else:
    def parse(source, filename='<unknown>', mode='exec', *,
            type_comments=False, feature_version=None):
        """
        Parse the source into an AST node.
        Equivalent to compile(source, filename, mode, PyCF_ONLY_AST).
        Pass type_comments=True to get back type comments where the syntax
        allows.
        """
        if type_comments:
            raise ValueError('type_comments was added to ast in Python 3.8')
        if feature_version is not None:
            raise ValueError('feature_version was added to ast in Python 3.8')
        flags = PyCF_ONLY_AST
        tree = compile(source, filename, mode, flags)
        return patch_tree(tree)
from ast import slice
from ast import stmt
try:
    from ast import type_ignore
except ImportError:
    type_ignore = TypeIgnore
from ast import unaryop
from ast import walk
from ast import withitem


class _PatchTree(NodeTransformer):
    def visit_arguments(self, node):
        node = self.generic_visit(node)

        try:
            node.posonlyargs
        except AttributeError:
            node.posonlyargs = []

        return node

    def visit_Module(self, node):
        node = self.generic_visit(node)

        try:
            node.type_ignores
        except AttributeError:
            node.type_ignores = []

        return node

    def visit_arg(self, node):
        node = self.generic_visit(node)

        try:
            node.type_comment
        except AttributeError:
            node.type_comment = None

        return node

    def visit_AsyncWith(self, node):
        node = self.generic_visit(node)

        try:
            node.type_comment
        except AttributeError:
            node.type_comment = None

        return node

    def visit_With(self, node):
        node = self.generic_visit(node)

        try:
            node.type_comment
        except AttributeError:
            node.type_comment = None

        return node

    def visit_AsyncFor(self, node):
        node = self.generic_visit(node)

        try:
            node.type_comment
        except AttributeError:
            node.type_comment = None

        return node

    def visit_For(self, node):
        node = self.generic_visit(node)

        try:
            node.type_comment
        except AttributeError:
            node.type_comment = None

        return node

    def visit_Assign(self, node):
        node = self.generic_visit(node)

        try:
            node.type_comment
        except AttributeError:
            node.type_comment = None

        return node

    def visit_AsyncFunctionDef(self, node):
        node = self.generic_visit(node)

        try:
            node.type_comment
        except AttributeError:
            node.type_comment = None

        return node

    def visit_FunctionDef(self, node):
        node = self.generic_visit(node)

        try:
            node.type_comment
        except AttributeError:
            node.type_comment = None

        return node


def patch_tree(tree):
    if isinstance(tree, list):
        return [patch_tree(el) for el in tree]

    tree = _copy.deepcopy(tree)
    return _PatchTree().visit(tree)
