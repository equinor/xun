import xun


some_ctx = xun.context(
    driver=xun.functions.driver.Sequential(),
    store=xun.functions.store.Memory(),
)


@xun.make_shared
def capitalize(msg):
    return msg[0].upper() + msg[1:]


@some_ctx.function()
def hello():
    return capitalize('hello')


@some_ctx.function()
def hello_world(receiver):
    return '{} {}!'.format(a, receiver)
    with ...:
        a = hello()
