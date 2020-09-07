#!/usr/bin/env python3

import xun


v = 3


@xun.make_shared
def add(a, b):
    return a + b


@xun.function()
def three():
    return v


@xun.function()
def add3(a):
    return add(a, thr)
    with ...:
        thr = three()


@xun.function()
def script(value):
    print("Result:", result)
    return result
    with ...:
        result = add3(value)


def main():
    script.blueprint(3).run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

if __name__ == '__main__':
    main()
