import xun


some_ctx = xun.context(
    driver=xun.functions.driver.Sequential(),
    store=xun.functions.store.Memory(),
)


@some_ctx.function()
def hello():
    return 'hello'


@some_ctx.function()
def hello_world(receiver):
    return '{} {}!'.format(a, receiver)
    with ...:
        a = hello()
