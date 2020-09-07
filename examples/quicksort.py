#!/usr/bin/env python3
import xun


"""
WARNING: in this example almost all the computations happens within the with
constants statement and will be run during scheduling. It cannot be
parallelized, and is indended only to show the syntax of with constants
statements.
"""


@xun.function()
def quicksort(iterable):
    result = []

    result.extend(lt_sorted)

    if len(pivot) == 1:
        result.append(pivot[0])

    result.extend(gt_sorted)

    return tuple(result)
    with ...:
        # Tuples are used because arguments must be hashable and lists are not
        lt_sorted = quicksort(lt) if len(lt) > 0 else tuple()
        gt_sorted = quicksort(gt) if len(gt) > 0 else tuple()

        # Workaround because generators can't be pickled, make list before tuple
        lt = tuple([item for item in L[1:] if item <= pivot[0]])
        gt = tuple([item for item in L[1:] if item  > pivot[0]])

        pivot = L[:1]
        L = list(iterable)


def main():
    input = (8, 4, 7, 5, 6, 0, 9, 2, 3, 1)

    print('input:', input)

    output = quicksort.blueprint(input).run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )

    print('output:', output)


if __name__ == '__main__':
    main()
