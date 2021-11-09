from hypothesis import given
from hypothesis.strategies import builds
from hypothesis.strategies import just
from hypothesis.strategies import lists
from hypothesis.strategies import none
from hypothesis.strategies import one_of
from hypothesis.strategies import recursive
from hypothesis.strategies import text
from string import ascii_lowercase
from string import ascii_uppercase
from string import digits
from xun.fs.queries import parse
from xun.fs.queries import syntax_tree as xst
from xun.fs.queries import unparse

###############################################################################
# Hypothesis query generation
#


alphas = text(
    alphabet=ascii_lowercase + ascii_uppercase, min_size=1, max_size=1
).map(str.strip).filter(bool)
alphanums_ = text(
    alphabet=ascii_lowercase + ascii_uppercase + digits + '_', min_size=1
).map(str.strip).filter(bool)


operators = one_of(just('='), just('>'), just('>='), just('<'), just('<='))
identifiers = builds(lambda a, an_: a + an_, alphas, alphanums_)
quoted_strings = builds(repr, text())
tags = one_of(
    builds(xst.Tag, identifiers, operators, quoted_strings),
    builds(xst.Tag, identifiers, none(), none()),
)
query_arguments = builds(xst.Arguments, lists(tags))
exprs = identifiers
leaves = builds(xst.Hierarchy, just(...), just([]))
trees = leaves | recursive(
    builds(xst.Hierarchy, exprs, lists(leaves, min_size=1, max_size=1)),
    lambda children: builds(xst.Hierarchy, exprs, lists(children, min_size=1)),
    max_leaves=5,
)
queries = builds(xst.Query, query_arguments, trees)


###############################################################################
# Tests
#


def test_query_language_basic():
    query = """
    (a aa bb<"0" cc<="0" dd>"00" ee>="00" ff="00") =>
        a {
            bb {
                ...
            }
            cc {
                dd {
                    ...
                }
            }
        }
    """
    result = parse(query)

    reference = xst.Query(
        xst.Arguments([
            xst.Tag(name='a', operator=None, value=None),
            xst.Tag(name='aa', operator=None, value=None),
            xst.Tag(name='bb', operator='<', value='"0"'),
            xst.Tag(name='cc', operator='<=', value='"0"'),
            xst.Tag(name='dd', operator='>', value='"00"'),
            xst.Tag(name='ee', operator='>=', value='"00"'),
            xst.Tag(name='ff', operator='=', value='"00"'),
        ]),
        xst.Hierarchy(
            'a',
            [
                xst.Hierarchy('bb', [
                    xst.Hierarchy(..., [])
                ]),
                xst.Hierarchy('cc', [
                    xst.Hierarchy('dd', [
                        xst.Hierarchy(..., [])
                    ]),
                ]),
            ],
        ),
    )

    assert result == reference


@given(queries)
def test_query_language_hypothesis(query):
    query_string = unparse(query)
    assert query == parse(query_string)
