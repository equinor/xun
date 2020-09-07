# Xùn

```
████████████████████████████████
████████████████████████████████


████████████████████████████████
████████████████████████████████


██████████████    ██████████████
██████████████    ██████████████

https://en.wikipedia.org/wiki/Bagua
```

# Tutorial

## Quick Start

Standalone example xun project file for computing fibonacci numbers

```python
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
        store=xun.functions.store.Memory(),
    )
    for num in sequence:
        print(num)


if __name__ == '__main__':
    main()
```

Note that the `main` function defined here is optional. This project could either be run as is, or run using xun. To run the program using xun, run the following:

```bash
xun exec examples/fibonacci.py "fibonacci_sequence(10)"
```

To see a visualization of the call graph:

```bash
xun graph examples/fibonacci.py "fibonacci_sequence(10)"
```

## A closer look

Let's break down the code from `fibonacci_number` in the example above in to 4 parts

```python
@context.function()
```
The decorator `@context.function()` marks this function as a context function, or a job. Context functions are functions that are meant to be executed in parallel, possibly on remote workers.

```python
def fibonacci_number(n):
```
The function definition is just normal a python function definition.
```python
    return f_n_1 + f_n_2
```
The body of the function is just regular python, it has as expected access to the function arguments, but it also has access to the variables defined in the special with constants statement.
```python
    with ...:
        f_n_1 = (
            0 if n == 0 else
            1 if n == 1 else
            fibonacci_number(n - 1)
        )
        f_n_2 = fibonacci_number(n - 2) if n > 1 else 0
```
Statements on form `with ...:` we refere to as with constant statments, they introduce new syntex and rules that we'll get move into in the next section. But important to note is that the recursive calls to `fibonacci_number(n)` are memoized in the context store, and can after scheduling, be run in parallel.

In fact, `xun` works by first figuring out all the calls that will happen to context functions, building a call graph, and scheduling the calls such that any previous call that we may depend on is executed before we evaluate the current call. This requires the call graph to be a DAG, or directed acyclic graph.

## With Constants Statement

```python
@context.function()
def do_some_work(some_values):
    result = expensive_computation(data)
    with ...:
        data = depencency(fixed_values)
        fixed_values = [fix(v) for v in some_values]
```

In the above example a job takes in some iterable, `some_values` as argument, polished the values in it and calls another context function that it depends on. Note that the order of the statements inside the with constants statements does not matter. The syntax of with constants statements is similar to where clauses in Haskell and has rules that differ from standard python. In general, for with constants statements the following apply:

* Order of statements is arbitrary
* Calling context functions is only allowed within with constants statements
* Only assignments and free expressions are allowed
* There can only be one with constants statements per context function
* Values cannot be modified
* If a function modifies a value passed to it, the changes will not be reflected for the value in the with constants statement
* Any code in with constants statements will be executed during scheduling, so the heavy lifting should be done in fully in the function body, and not inside the with constants statements

With constants statements allows xun to figure out the order of calls needed to execute a xun program.

## Stores

```python
class DiskCache(metaclass=StoreMeta):
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir

    def __contains__(self, key):
        with diskcache.Cache(self.cache_dir) as cache:
            return key in cache

    def __delitem__(self, key):
        with diskcache.Cache(self.cache_dir) as cache:
            del cache[key]

    def __getitem__(self, key):
        with diskcache.Cache(self.cache_dir) as cache:
            return cache[key]

    def __iter__(self):
        with diskcache.Cache(self.cache_dir) as cache:
            return iter(cache)

    def __len__(self):
        with diskcache.Cache(self.cache_dir) as cache:
            return len(cache)

    def __setitem__(self, key, value):
        with diskcache.Cache(self.cache_dir) as cache:
            cache[key] = value
```

As calls to context functions are executed and finished, the results are saved in the store of the context. Stores are classes that satisfy the requirements of `collections.abc.MutableMapping`, are pickleable, and whos state is shared between all instances. Stores can be defined by users by specifying a class with metaclass `xun.functions.store.StoreMeta`. The above code is in fact the entire implementation of the `xun.functions.store.DiskCache` store.

## Drivers

Drivers are the classes that have the responsibility of executing programs. This includes scheduling the calls of the call graph and managing any concurency.

## The `@xun.make_shared` decorator

```python
from math import radians
import numpy as np


def not_installed():
    pass


@xun.make_shared
def not_installed_but_shared():
    pass


@context.function()
def context_function():
    not_installed()            # Not OK
    not_installed_but_shared() # OK
    radians(180)               # OK because the function is builtin
    np.array([1, 2, 3])        # OK because the function is defined in an installed module
```

Because context functions are pickled, any function they reference must either be installed on the system, be represented differently. `xun` comes with a decorator, `@xun.make_shared`, that can make many functions serializable, which you need to use if you wish to call functions defined in your project file.
