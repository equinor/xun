import xun


context = xun.context(
    driver=xun.functions.driver.Local(),
    store=xun.functions.store.Memory(),
)


v = 3


def add(a, b):
    return a + b


@context.function()
def three():
    return v


@context.function()
def add3(a):
    return add(a, three)
    with ...:
        three = three()


@context.function()
def script():
    return result
    with ...:
        result = add3(2)


program = context.script.compile()
print(program())
