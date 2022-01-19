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
import ast


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

def parse_operator(tokens):
    op_str, = tokens
    return op_str


def parse_value(token):
    value, = token
    return ast.literal_eval(value)


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
    for h in hierarchy:
        expr, children = h

        if children != ...:
            children = list(children)

        yield syntax_tree.Hierarchy(expr, children)


def parse_arguments(arguments):
    return syntax_tree.Arguments(list(arguments))


def parse_query(query):
    arguments, hierarchy = query

    if hierarchy != ...:
        hierarchy = list(hierarchy)

    return syntax_tree.Query(arguments, hierarchy)


###############################################################################
# Grammar specification
#


arrow = Suppress('=>')
lparen, rparen = Suppress('('), Suppress(')')
lbrace, rbrace = Suppress('{'), Suppress('}')


identifier = Word(alphas + '_', alphanums + '_')
operator = oneOf('= > >= < <=')
operator.setParseAction(parse_operator)
value = quotedString.setParseAction(parse_value)
tag_specifier = identifier + operator + value
tag = tag_specifier | identifier
tag = tag.setParseAction(parse_tag)


expr = identifier
leaf = Literal('...')
leaf.setParseAction(lambda _: ...)
hierarchy = Forward()
hierarchy <<= leaf | Group(
    OneOrMore(
        Group(expr + lbrace + hierarchy + rbrace)
    ).setParseAction(parse_hierarchy),
)


arguments = lparen + ZeroOrMore(tag) + rparen
arguments.setParseAction(parse_arguments)


query_string = arguments + arrow + hierarchy
query_string.setParseAction(parse_query)
