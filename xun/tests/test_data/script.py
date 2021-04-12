import xun


@xun.make_shared
def capitalize(msg):
    return msg[0].upper() + msg[1:]


@xun.function()
def hello():
    return capitalize('hello')


@xun.function()
def hello_world(receiver):
    return '{} {}!'.format(a, receiver)
    with ...:
        a = hello()


@xun.function()
def f(*args, **kwargs):
    pass


@xun.function()
def g(*args, **kwargs):
    pass
