from collections import namedtuple
from pyparsing import Forward
from pyparsing import Group
from pyparsing import Literal
from pyparsing import OneOrMore
from pyparsing import Suppress
from pyparsing import Word
from pyparsing import ZeroOrMore
from pyparsing import alphanums
from pyparsing import alphas
from pyparsing import oneOf
from pyparsing import quotedString
from types import SimpleNamespace


###############################################################################
# Syntax Tree
#

syntax_tree = SimpleNamespace(
    Tag=namedtuple('Tag', 'name operator value'),
    Arguments=namedtuple('Arguments', 'args'),
    Hierarchy=namedtuple('Hierarchy', 'expr children'),
    Query=namedtuple('Query', 'arguments hierarchy'),
)


###############################################################################
# Parser functions
#

def parse_tag(tag):
    if len(tag) == 3:
        name, operator, value = tag
        return syntax_tree.Tag(name, operator, value)
    elif len(tag) == 1:
        name, = tag
        return syntax_tree.Tag(name, None, None)
    else:
        raise RuntimeError('Tag parser error')


def parse_hierarchy(hierarchy):
    expr, *children = hierarchy
    expr = ... if expr == '...' else expr

    if expr == ... and len(children) > 0:
        raise ValueError('file node (...) cannot have expr nodes')
    if expr != ... and len(children) == 0:
        msg = f'directory node ({expr}) must have at least one child'
        raise ValueError(msg)

    return syntax_tree.Hierarchy(expr, list(children))


def parse_arguments(arguments):
    return syntax_tree.Arguments(list(arguments[0]))


def parse_query(query):
    arguments, tree = query
    return syntax_tree.Query(arguments, tree)


###############################################################################
# Grammar specification
#


arrow = Suppress('=>')
lparen, rparen = Suppress('('), Suppress(')')
lbrace, rbrace = Suppress('{'), Suppress('}')


operator = oneOf('= > >= < <=')
identifier = Word(alphas + '_', alphanums + '_')
tag_specifier = identifier + operator + quotedString
tag = tag_specifier | identifier
tag = tag.setParseAction(parse_tag)


leaf = Literal('...')
leaf.setParseAction(parse_hierarchy)
expr = identifier
hierarchy = Forward()
hierarchy <<= leaf
hierarchy <<= expr + lbrace + OneOrMore(hierarchy | leaf) + rbrace
hierarchy = hierarchy.setParseAction(parse_hierarchy)


arguments = lparen + Group(ZeroOrMore(tag)) + rparen
arguments.setParseAction(parse_arguments)


query_string = arguments + arrow + (hierarchy | leaf)
query_string.setParseAction(parse_query)
