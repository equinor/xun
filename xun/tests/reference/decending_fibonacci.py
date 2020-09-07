import xun
from .decending_sort import decending_sort
from .fibonacci import fibonacci_sequence


@xun.function()
def decending_fibonacci(n):
    with ...:
        fs = fibonacci_sequence(n)
        decending = decending_sort(fs)
    return decending
