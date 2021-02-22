#!/usr/bin/env python3
import xun


"""
TODO, not good use, but! it works cause of automatic memoization
"""


@xun.function()
def fibonacci_number(n):
    return f_n_1 + f_n_2
    with ...:
        f_n_1 = (
            0 if n == 0 else
            1 if n == 1 else
            fibonacci_number(n - 1)
        )
        f_n_2 = fibonacci_number(n - 2) if n > 1 else 0


@xun.function()
def fibonacci_sequence(n):
    return sequence
    with ...:
        sequence = [fibonacci_number(i) for i in range(n)]


def main():
    """
    Compute and print the first 10 fibonacci numbers
    """
    blueprint = fibonacci_sequence.blueprint(10)
    sequence = blueprint.run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Disk('store'),
    )
    for num in sequence:
        print(num)


if __name__ == '__main__':
    main()
