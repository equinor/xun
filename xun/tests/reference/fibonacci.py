import xun


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
    return tuple(sequence)
    with ...:
        sequence = [fibonacci_number(i) for i in range(n)]
