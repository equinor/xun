import xun

def test_unpack():
    cn = xun.functions.graph.CallNode('f')

    shape = 3
    a = cn.unpack(shape)
    assert a == (cn, cn, cn)

    shape = (1, 2)
    a = cn.unpack(shape)
    assert a == (cn, (cn, cn))

    shape = (1, 1, 2)
    a = cn.unpack(shape)
    assert a == (cn, cn, (cn, cn))

    shape = (2, 2)
    a = cn.unpack(shape)
    assert a == ((cn, cn), (cn, cn))

    shape = (1, (1, 1, 2), 1)
    a = cn.unpack(shape)
    assert a == (cn, (cn, cn, (cn, cn)), cn)

    shape = (1, (3, 2), 1)
    a = cn.unpack(shape)
    assert a == (cn, ((cn, cn, cn), (cn, cn)), cn)

    shape = (1, 1, 0)
    a = cn.unpack(shape)
    assert a == (cn, cn, [cn])
