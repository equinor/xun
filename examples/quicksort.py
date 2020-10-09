#!/usr/bin/env python3
import xun


"""
WARNING: in this example almost all the computations happen within the with
constants statement and will be run during scheduling. It cannot be
parallelized, and is indended only to show the syntax of with constants
statements.

Note that this quicksort only accepts hashable iterables. We therefore need to
use tuples instead of lists. This is a limitiation of xun, because arguments
are hashed in the call graph.
"""


@xun.function()
def quicksort(hashable_iterable):
    result = []

    result.extend(le_sorted)

    if len(pivot) == 1: # It is 0 if the list is empty
        result.append(pivot[0])

    result.extend(gt_sorted)

    return tuple(result)
    with ...:
        # Tuples are used because arguments must be hashable and lists are not
        le_sorted = quicksort(le) if len(le) > 0 else tuple()
        gt_sorted = quicksort(gt) if len(gt) > 0 else tuple()

        # Workaround because generators can't be pickled, make list before tuple
        le = tuple([item for item in L[1:] if item <= pivot[0]])
        gt = tuple([item for item in L[1:] if item  > pivot[0]])

        L = list(hashable_iterable)
        pivot = L[:1]


def main():
    input = (
        16, 10, 12, 2, 20, 1, 13, 0, 7, 4, 8, 5, 14, 15, 9, 17, 21, 23, 18, 11,
        19, 22, 6, 3
    )

    print('input:', input)

    output = quicksort.blueprint(input).run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    print('output:', output)


if __name__ == '__main__':
    main()
