from xun.functions.graph import CallNode
from xun.functions.runtime import unpack


def test_unpack_python_types():
    a0, b0, c0 = unpack((3,), [1, 2, 3])
    a1, b1, c1 = unpack((3,), (1, 2, 3))
    a2, b2, c2 = unpack((3,), {1: 1, 2: 2, 3: 3})
    a3, b3, c3 = unpack((3,), range(1, 4))
    assert a0 == a1 == a2 == a3
    assert b0 == b1 == b2 == b3
    assert c0 == c1 == c2 == c3

    a = [1, 2, 3]
    b = [4, 5, 6]
    [a0, b0], [a1, b1], [a2, b2] = unpack(((2,), (2,), (2,)), zip(a, b))
    assert [a0, a1, a2] == a
    assert [b0, b1, b2] == b


def test_unpack():
    cn = CallNode('f', None)

    assert cn[0] == cn[0]
    assert not cn[0] == cn[1]

    shape = (1, )  # The CallNode value is an iterable containing one item
    a = tuple(unpack(shape, cn))
    expected = (cn[0],)
    assert a == expected

    shape = (1, ((3,), (2,)), 1)
    (a, ((b, c, d), (e, f)), g) = unpack(shape, cn)
    expected = (
        cn[0],
        (
            (
                cn[1][0][0],
                cn[1][0][1],
                cn[1][0][2],
            ),
            (
                cn[1][1][0],
                cn[1][1][1],
            ),
        ),
        cn[2],
    )
    assert (a, ((b, c, d), (e, f)), g) == expected


def test_unpack_starred():
    cn = CallNode('f', None)

    shape = (2, Ellipsis)
    a, b, c = unpack(shape, cn)
    expected = (cn[0], cn[1], cn[2:])
    assert (a, b, c) == expected

    shape = (1, Ellipsis, 2)
    a, b, c, d = unpack(shape, cn)
    expected = (cn[0], cn[1:-2], cn[-2], cn[-1])
    assert (a, b, c, d) == expected

    shape = (1, (1, Ellipsis), Ellipsis)
    (x, (y, ys), xs) = unpack(shape, cn)
    expected = (cn[0], (cn[1][0], cn[1][1:]), cn[2:])
    assert (x, (y, ys), xs) == expected
