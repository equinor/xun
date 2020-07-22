#!/usr/bin/env python3
import xun


context = xun.context(
    driver=xun.functions.driver.Sequential(),
    store=xun.functions.store.DiskCache('store'),
)


@context.function()
def fibonacci_number(n):
    return f_n_1 + f_n_2
    with ...:
        f_n_1 = (
            0 if n == 0 else
            1 if n == 1 else
            fibonacci_number(n - 1)
        )
        f_n_2 = fibonacci_number(n - 2) if n > 1 else 0


@context.function()
def fibonacci_sequence(n):
    return sequence
    with ...:
        sequence = [fibonacci_number(i) for i in range(n)]


def main():
    """
    Compute and print the first 10 fibonacci numbers
    """
    program = context.fibonacci_sequence.compile(10)
    sequence = program()
    for num in sequence:
        print(num)


if __name__ == '__main__':
    main()
