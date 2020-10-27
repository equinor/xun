from xun.functions.graph import CallNode
from xun.functions.graph import CallNodeSubscript
import pytest
import xun


def test_unpack():
    cn = CallNode('f')

    assert CallNodeSubscript(cn, (0, )) == CallNodeSubscript(cn, (0, ))
    assert not CallNodeSubscript(cn, (0, )) == CallNodeSubscript(cn, (1, ))

    shape = (1, )
    a = cn.unpack(shape)
    required = (CallNodeSubscript(cn, (0, )), )
    assert a == required

    shape = (3, )
    a = cn.unpack(shape)
    required = (
        CallNodeSubscript(cn, (0, )),
        CallNodeSubscript(cn, (1, )),
        CallNodeSubscript(cn, (2, )),
    )
    assert a == required

    shape = (1, (2,))
    a = cn.unpack(shape)
    required = (
        CallNodeSubscript(cn, (0, )),
        (
            CallNodeSubscript(cn, (1, 0)),
            CallNodeSubscript(cn, (1, 1)),
        ),
    )
    assert a == required

    shape = (1, 1, (2,))
    a = cn.unpack(shape)
    required = (
        CallNodeSubscript(cn, (0, )),
        CallNodeSubscript(cn, (1, )),
        (
            CallNodeSubscript(cn, (2, 0)),
            CallNodeSubscript(cn, (2, 1)),
        ),
    )
    assert a == required

    shape = ((2,), (2,))
    a = cn.unpack(shape)
    required = (
        (
            CallNodeSubscript(cn, (0, 0)),
            CallNodeSubscript(cn, (0, 1)),
        ),
        (
            CallNodeSubscript(cn, (1, 0)),
            CallNodeSubscript(cn, (1, 1)),
        ),
    )
    assert a == required

    shape = (1, (1, 1, (2,)), 1)
    a = cn.unpack(shape)
    required = (
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
    assert a == required

    shape = (1, ((3,), (2,)), 1)
    a = cn.unpack(shape)
    required = (
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
    assert a == required


def test_unpack_starred():
    cn = CallNode('f')

    shape = (1, 1, 0)
    a = cn.unpack(shape)
    required = (
        CallNodeSubscript(cn, (0, )),
        CallNodeSubscript(cn, (1, )),
        CallNodeSubscript([cn], (2, )),
    )
    assert a == required

    shape = (1, (1, 0), 0)
    a = cn.unpack(shape)
    required = (
        CallNodeSubscript(cn, (0, )),
        (
            CallNodeSubscript(cn, (1, 0)),
            CallNodeSubscript([cn], (1, 1)),
        ),
        CallNodeSubscript([cn], (2, )),
    )
    assert a == required
