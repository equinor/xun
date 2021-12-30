from . import grammar


def parse(query_string):
    """ Parse

    Returns
    -------
    xun.fs.queries.syntax_tree.Query
        The root of the abstract syntax tree
    """
    ast, = grammar.query_string.parseString(query_string, parseAll=True)
    return ast


def unparse(query_syntax_tree):
    """ Unparse

    Returns
    -------
    str
        Query string that would parse to the given abstract syntax tree
    """

    class Unparse:
        """
        Converts nodes in an abstract syntax tree to strings
        """

        @classmethod
        def visit(cls, node):
            member = 'visit_' + node.__class__.__name__
            visitor = getattr(cls, member)
            return visitor(node)

        @staticmethod
        def visit_Arguments(node):
            args = ' '.join(Unparse.visit(arg) for arg in node.args)
            return f'({args})'

        @staticmethod
        def visit_Tag(node):
            if node.operator is not None:
                return f'{node.name}{node.operator}{repr(node.value)}'
            else:
                return node.name

        @staticmethod
        def visit_ellipsis(node):
            return '...'

        @staticmethod
        def visit_Hierarchy(node):
            try:
                c = ' '.join(Unparse.visit(child) for child in node.children)
            except TypeError:
                c = Unparse.visit(node.children)
            return f'{node.expr} {{ {c} }}'

        @staticmethod
        def visit_Query(node):
            args = Unparse.visit(node.arguments)
            try:
                tree = [Unparse.visit(h) for h in node.hierarchy]
            except TypeError:
                tree = [Unparse.visit(node.hierarchy)]
            return f'{args} => {" ".join(tree)}'
    return Unparse.visit(query_syntax_tree)
