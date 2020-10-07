from xun.functions.compatibility import ast as compat_ast
import ast
import sys


major_version = sys.version_info[0]
minor_version = sys.version_info[1]


def test_Constant():
    constant_int = compat_ast.Constant(5, None)
    constant_float = compat_ast.Constant(5.5, None)
    constant_complex = compat_ast.Constant(5.5 + 5j, None)
    constant_string = compat_ast.Constant("hello", None)
    constant_bytes = compat_ast.Constant(b"0042", None)
    constant_nameconstant_bool = compat_ast.Constant(True, None)
    constant_nameconstant_none = compat_ast.Constant(None, None)
    constant_ellipsis = compat_ast.Constant(..., None)

    assert isinstance(constant_int, compat_ast.Constant)
    assert isinstance(constant_float, compat_ast.Constant)
    assert isinstance(constant_complex, compat_ast.Constant)
    assert isinstance(constant_string, compat_ast.Constant)
    assert isinstance(constant_bytes, compat_ast.Constant)
    assert isinstance(constant_nameconstant_bool, compat_ast.Constant)
    assert isinstance(constant_nameconstant_none, compat_ast.Constant)
    assert isinstance(constant_ellipsis, compat_ast.Constant)

    if major_version >= 3 and minor_version >= 8:
        assert compat_ast.Constant is ast.Constant
    else:
        assert type(constant_int) is ast.Num
        assert type(constant_float) is ast.Num
        assert type(constant_complex) is ast.Num
        assert type(constant_string) is ast.Str
        assert type(constant_bytes) is ast.Bytes
        assert type(constant_nameconstant_bool) is ast.NameConstant
        assert type(constant_nameconstant_none) is ast.NameConstant
        assert type(constant_ellipsis) is ast.Ellipsis


def test_parse_patch():
    tree = compat_ast.parse('def f(): pass')
    assert hasattr(tree, 'type_ignores')
    assert hasattr(tree.body[0], 'type_comment')
