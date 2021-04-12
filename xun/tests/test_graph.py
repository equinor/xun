from xun.functions.graph import CallNode


def test_unpack():
    cn = CallNode('f', None)

    assert cn[0] == cn[0]
    assert not cn[0] == cn[1]

    shape = (1, )  # The CallNode value is an iterable containing one item
    a = cn.unpack(shape)
    expected = (cn[0],)
    assert a == expected

    shape = (3, )
    a = cn.unpack(shape)
    expected = (
        cn[0],
        cn[1],
        cn[2],
    )
    assert a == expected

    shape = (2, (2,))
    a = cn.unpack(shape)
    expected = (
        cn[0],
        cn[1],
        (
            cn[2][0],
            cn[2][1],
        ),
    )
    print(a)
    assert a == expected

    shape = ((2,), (2,))
    a = cn.unpack(shape)
    expected = (
        (
            cn[0][0],
            cn[0][1],
        ),
        (
            cn[1][0],
            cn[1][1],
        ),
    )
    assert a == expected

    shape = (1, (2, (2,)), 1)
    a = cn.unpack(shape)
    expected = (
        cn[0],
        (
            cn[1][0],
            cn[1][1],
            (
                cn[1][2][0],
                cn[1][2][1],
            ),
        ),
        cn[2],
    )
    assert a == expected

    shape = (1, ((3,), (2,)), 1)
    a = cn.unpack(shape)
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
    assert a == expected


def test_unpack_starred():
    cn = CallNode('f', None)

    shape = (2, Ellipsis)
    a = cn.unpack(shape)
    expected = (
        cn[0],
        cn[1],
        cn[2],
    )
    assert a == expected

    shape = (1, (1, Ellipsis), Ellipsis)
    a = cn.unpack(shape)
    expected = (
        cn[0],
        (
            cn[1][0],
            cn[1][1],
        ),
        cn[2],
    )
    assert a == expected
