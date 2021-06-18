"""Xun typing

This module provide a typing system for the xun environment.

Types used are:
* XunType: call to a xun function
* Any: everything else
* Tuple: several possible different types, one for each element of the tuple
* List: one type that denotes the entire list
* Union
* TerminalType: can be returned, but not be reused in comprehensions
"""


from .compatibility import ast
from .errors import XunSyntaxError
from .util import assignment_target_shape
from .util import flatten_assignment_targets
from .util import indices_from_shape
from immutables import Map as frozenmap
import typing


class XunType:
    def __call__(self, *args, **kwargs):
        raise TypeError('XunType should not be used')

    def __repr__(self):
        return self.__class__.__name__
XunType = XunType()


class TerminalType:
    def __call__(self, *args, **kwargs):
        raise TypeError('TerminalType should not be used')

    def __getitem__(self, key):
        inst = self.__class__.__new__(self.__class__)
        inst.generic_type = key
        return inst

    def __repr__(self):
        r = self.__class__.__name__
        if hasattr(self, 'generic_type'):
            r += f'[{self.generic_type}]'
        return r
TerminalType = TerminalType()


def type_not_allowed_error(node):
    return XunSyntaxError(f'{node.__class__} not allowed in xun definitions')


def is_tuple_type(t):
    # Python 3.6 operates with t.__origin__ is typing.Tuple, but for >3.6 it
    # is t.__origin__ is tuple
    return hasattr(t, '__origin__') and (
        t.__origin__ is tuple or t.__origin__ is typing.Tuple)


def is_list_type(t):
    return hasattr(t, '__origin__') and (
        t.__origin__ is list or t.__origin__ is typing.List)


def is_set_type(t):
    return hasattr(t, '__origin__') and (
        t.__origin__ is set or t.__origin__ is typing.Set)


def is_xun_type(t):
    return t is XunType


def is_iterator_type(t):
    return t is typing.Iterator


class TypeDeducer:
    """
    Registers all variables and their types
    """
    def __init__(self, known_xun_functions):
        self.known_xun_functions = known_xun_functions
        self.with_names = []
        self.expr_name_type_map = frozenmap()

    def _replace(self, **kwargs):
        """
        Replace the existing values of class attributes with new ones.

        Parameters
        ----------
        kwargs : dict
            keyword arguments corresponding to one or more attributes whose
            values are to be modified

        Returns
        -------
        A new class instance with replaced attributes
        """
        attribs = {k: kwargs.pop(k, v) for k, v in vars(self).items()}
        if kwargs:
            raise ValueError(f'Got unexpected field names: {list(kwargs)!r}')
        inst = self.__class__.__new__(self.__class__)
        inst.__dict__.update(attribs)
        return inst

    def visit(self, node):
        member = 'visit_' + node.__class__.__name__
        visitor = getattr(self, member)
        return visitor(node)

    def visit_Assign(self, node):
        if len(node.targets) > 1:
            raise SyntaxError("Multiple targets not supported")

        target = node.targets[0]
        target_shape = assignment_target_shape(target)

        value_type = self.visit(node.value)

        if target_shape == (1,):
            self.with_names.append(target.id)
            with self.expr_name_type_map.mutate() as mm:
                mm[target.id] = value_type
                self.expr_name_type_map = mm.finish()
            return value_type

        indices = indices_from_shape(target_shape)
        flatten_targets = flatten_assignment_targets(target)

        with self.expr_name_type_map.mutate() as mm:
            for index, target in zip(indices, flatten_targets):
                self.with_names.append(target.id)
                target_type = value_type
                if is_list_type(target_type):
                    target_type = target_type.__args__[0]
                for i in index:
                    if is_tuple_type(target_type):
                        target_type = target_type.__args__[i]
                    elif is_list_type(target_type):
                        target_type = target_type.__args__[0]
                mm.set(target.id, target_type)
            new_map = mm.finish()
        self.expr_name_type_map = new_map

        return value_type

    def visit_BoolOp(self, node):
        raise NotImplementedError

    def visit_BinOp(self, node):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        if left_type is XunType or right_type is XunType:
            raise XunSyntaxError(
                'Cannot use xun function results as values in xun '
                'definition'
            )
        return typing.Any

    def visit_UnaryOp(self, node):
        raise NotImplementedError

    def visit_IfExp(self, node):
        body_type = self.visit(node.body)
        orelse_type = self.visit(node.orelse)
        if body_type is not orelse_type:
            return TerminalType[typing.Union[body_type, orelse_type]]
        return body_type

    def visit_Dict(self, node: ast.Dict):
        """ We don't support xun keys
        Unknown type, because we can't reason about it (new issue)
        Hence, you can't forward it
        Weak coupling between keys and values
        """
        return TerminalType[typing.Dict]

    def visit_Set(self, node):
        """
        Since unordered, all types must be the same
        """
        set_type = self.visit(node.elts[0])
        for elt in node.elts:
            elt_type = self.visit(elt)
            if elt_type is not set_type:
                raise XunSyntaxError
        return typing.Set[set_type]

    def visit_ListComp(self, node: ast.ListComp):
        """
        ListComps in Xun produces Tuples (because of posibility for different
        types) -> ListComp means Tuple Comprehension
        Not allowed to iterate over tuples
        Iterator of generators can only be a variable, or a
        Does not support ifs or is_async

        TODO
        my_iter -> Tuple[Any, Xun, Any, Xun]
        [i for i in my_iter] -> Tuple[Any, Xun, Any, Xun]

        Result will be a list where all elements have the same type
        """
        return typing.List[self.visit_comp(node)]

    def visit_SetComp(self, node):
        # Example: {i for i in range(10)}
        # Terminal Type, can't be reused in comprehension
        # This must be of one type
        # Get something that must have same type
        # TODO: If uniform type ->
        return typing.Set[self.visit_comp(node)]

    def visit_DictComp(self, node):
        # Example: {k: v for k, v in ...}
        # Terminal Type, can't be reused in comprehension
        # This must be of one type
        return TerminalType[typing.Dict]

    def visit_GeneratorExp(self, node):
        # Example: (i for i in range(10))
        # This works
        # Terminal type or this becomes a list
        return typing.Iterator

    def visit_Await(self, node):
        raise type_not_allowed_error(node)

    def visit_Yield(self, node):
        raise type_not_allowed_error(node)

    def visit_YieldFrom(self, node):
        raise type_not_allowed_error(node)

    def visit_Compare(self, node):
        raise type_not_allowed_error(node)

    def visit_Call(self, node):
        if (isinstance(node.func, ast.Name)
                and node.func.id in self.known_xun_functions):
            return XunType
        return typing.Any

    def visit_FormattedValue(self, node):
        raise NotImplementedError

    def visit_JoinedStr(self, node):
        raise NotImplementedError

    def visit_Constant(self, node):
        return typing.Any

    def visit_Attribute(self, node):
        raise NotImplementedError

    def visit_Subscript(self, node):
        return self.visit(node.value)

    def visit_Starred(self, node):
        raise NotImplementedError

    def visit_Name(self, node: ast.Name):
        if node.id in self.expr_name_type_map.keys():
            return self.expr_name_type_map[node.id]
        return typing.Any

    def visit_List(self, node):
        return self.visit_Tuple(node)

    def visit_Tuple(self, node):
        return typing.Tuple[tuple(self.visit(elt) for elt in node.elts)]

    def visit_Slice(self, node):
        raise NotImplementedError

    #
    # For 3.6 compatibility
    #

    def visit_Num(self, node):
        return typing.Any

    def visit_Str(self, node):
        return typing.Any

    def visit_Bytes(self, node):
        return typing.Any

    def visit_NameConstant(self, node):
        return typing.Any

    def visit_Ellipsis(self, node):
        return typing.Any

    #
    # Helper methods
    #

    def visit_comp(self, node):
        # Register the local variables in each generator
        with self.expr_name_type_map.mutate() as local_scope:
            for generator in node.generators:
                iter_types = self.visit(generator.iter)

                target = generator.target
                target_shape = assignment_target_shape(target)

                if target_shape == (1,):
                    if is_xun_type(iter_types):
                        raise XunSyntaxError(
                            'CallNode not allowed in iterator')
                    local_scope.set(target.id, iter_types)
                    continue

                indices = indices_from_shape(target_shape)
                flatten_targets = flatten_assignment_targets(target)

                for index, target in zip(indices, flatten_targets):
                    target_type = iter_types
                    if is_list_type(target_type):
                        target_type = target_type.__args__[0]
                    for i in index:
                        if is_tuple_type(target_type):
                            target_type = target_type.__args__[i]
                        elif is_list_type(target_type):
                            target_type = iter_types.__args__[0]
                    local_scope.set(target.id, target_type)

            # Add mapping over known local variables while visiting the element
            # of the comprehension
            return self._replace(
                expr_name_type_map=local_scope.finish()).visit(node.elt)
