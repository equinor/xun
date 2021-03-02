from xun.functions.graph import CallNode
from xun.functions.graph import CallNodeSubscript


def test_unpack():
    cn = CallNode('f')

    assert CallNodeSubscript(cn, (0, )) == CallNodeSubscript(cn, (0, ))
    assert not CallNodeSubscript(cn, (0, )) == CallNodeSubscript(cn, (1, ))

    shape = (1, )  # The CallNode value is an iterable containing one item
    a = cn.unpack(shape)
    expected = (CallNodeSubscript(cn, (0, )), )
    assert a == expected

    shape = (3, )
    a = cn.unpack(shape)
    expected = (
        CallNodeSubscript(cn, (0, )),
        CallNodeSubscript(cn, (1, )),
        CallNodeSubscript(cn, (2, )),
    )
    assert a == expected

    shape = (2, (2,))
    a = cn.unpack(shape)
    expected = (
        CallNodeSubscript(cn, (0, )),
        CallNodeSubscript(cn, (1, )),
        (
            CallNodeSubscript(cn, (2, 0)),
            CallNodeSubscript(cn, (2, 1)),
        ),
    )
    assert a == expected

    shape = ((2,), (2,))
    a = cn.unpack(shape)
    expected = (
        (
            CallNodeSubscript(cn, (0, 0)),
            CallNodeSubscript(cn, (0, 1)),
        ),
        (
            CallNodeSubscript(cn, (1, 0)),
            CallNodeSubscript(cn, (1, 1)),
        ),
    )
    assert a == expected

    shape = (1, (2, (2,)), 1)
    a = cn.unpack(shape)
    expected = (
        CallNodeSubscript(cn, (0, )),
        (
            CallNodeSubscript(cn, (1, 0)),
            CallNodeSubscript(cn, (1, 1)),
            (
                CallNodeSubscript(cn, (1, 2, 0)),
                CallNodeSubscript(cn, (1, 2, 1)),
            ),
        ),
        CallNodeSubscript(cn, (2, )),
    )
    assert a == expected

    shape = (1, ((3,), (2,)), 1)
    a = cn.unpack(shape)
    expected = (
        CallNodeSubscript(cn, (0, )),
        (
            (
                CallNodeSubscript(cn, (1, 0, 0)),
                CallNodeSubscript(cn, (1, 0, 1)),
                CallNodeSubscript(cn, (1, 0, 2)),
            ),
            (
                CallNodeSubscript(cn, (1, 1, 0)),
                CallNodeSubscript(cn, (1, 1, 1)),
            ),
        ),
        CallNodeSubscript(cn, (2, )),
    )
    assert a == expected


def test_unpack_starred():
    cn = CallNode('f')

    shape = (2, Ellipsis)
    a = cn.unpack(shape)
    expected = (
        CallNodeSubscript(cn, (0, )),
        CallNodeSubscript(cn, (1, )),
        CallNodeSubscript(cn, (2, )),
    )
    assert a == expected

    shape = (1, (1, Ellipsis), Ellipsis)
    a = cn.unpack(shape)
    expected = (
        CallNodeSubscript(cn, (0, )),
        (
            CallNodeSubscript(cn, (1, 0)),
            CallNodeSubscript(cn, (1, 1)),
        ),
        CallNodeSubscript(cn, (2, )),
    )
    assert a == expected
