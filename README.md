# Xùn

<img src="docs/xun.svg" width="170" height="170">

https://en.wikipedia.org/wiki/Bagua

---

[![equinor](https://circleci.com/gh/equinor/xun.svg?style=shield)](https://app.circleci.com/pipelines/github/equinor/xun)

Xun is a distributed and functional Python framework for cluster compute. Rather than focusing on batching jobs, xun is about defining values declaratively.

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

To see a visualization of the call graph:

```bash
xun graph examples/fibonacci.py "fibonacci_sequence(10)"
```

## A closer look

Let's break down the code from `fibonacci_number` in the example above in to 4 parts

```python
@xun.function()
```

The decorator `@xun.function()` compiles this function into a xun function. Xun functions are functions that are meant to be executed in parallel, possibly on remote workers.

```python
def fibonacci_number(n):
```

The function definition is just a normal python function definition.

```python
    return f_n_1 + f_n_2
```

The body of the function is just regular python, it has as expected access to the function arguments, but it also has access to the variables defined in the special xun definitions statement.

```python
    with ...:
        f_n_1 = (
            0 if n == 0 else
            1 if n == 1 else
            fibonacci_number(n - 1)
        )
        f_n_2 = fibonacci_number(n - 2) if n > 1 else 0
```
Statements on the form `with ...:` we refer to as xun definitions. They introduce new syntax and rules that we will get more into in the next section. Note for example that the recursive calls to `fibonacci_number(n)` are memoized in the context store and can therefore, after scheduling, be run in parallel.

In fact, `xun` works by first figuring out all the calls that will happen, building a call graph, and scheduling the calls such that any previous call that we may depend on is executed before we evaluate the current call. This requires the call graph to be a directed acyclic graph (DAG).

## Xun Definitions

```python
@xun.function()
def do_some_work(some_values):
    result = expensive_computation(data)
    with ...:
        data = depencency(fixed_values)
        fixed_values = [fix(v) for v in some_values]
```

In the above example, a job takes in some iterable `some_values` as argument, polishes the values in it and calls another context function that it depends on. Note that the order of the statements inside the xun defintions statements does not matter. The syntax of xun definitions statements is similar to where clauses in Haskell and has rules that differ from standard python. In general, for xun definitions statements the following apply:

* Order of statements is arbitrary
* Xun functions can only be called from xun definition statements (`with ...:`)
* Only assignments and free expressions are allowed
* There can only be one xun definitions statement per xun function
* Values cannot be modified
* If a function modifies a value passed to it, the changes will not be reflected for the value in the definitions. That is, arguments to calls are passed by value.
* Any code in xun definitions statements will be executed during scheduling, so the heavy lifting should be done in the function body, and not inside the xun definitions statements

Xun definition statements allow xun to figure out the order of calls needed to execute a xun program.

## Stores

As calls to xun functions are executed and finished, the results are saved in the store of the context. Stores are classes that satisfy the requirements of `collections.abc.MutableMapping`, are pickleable, and whos state is shared between all instances. Stores can be defined by users by defining a new class with extending `xun.functions.store.Store`.

## Drivers

Drivers are the classes that have the responsibility of executing programs. This includes scheduling the calls of the call graph and managing any concurrency.

## The `@xun.make_shared` decorator

```python
from math import radians
import numpy as np


def not_installed():
    pass


@xun.make_shared
def not_installed_but_shared():
    pass


@xun.function()
def xun_function():
    not_installed()            # Not OK
    not_installed_but_shared() # OK
    radians(180)               # OK because the function is builtin
    np.array([1, 2, 3])        # OK because the function is defined in an installed module
```

Because xun functions are pickled, any function they reference must either be installed on the system or be represented differently. `xun` comes with a decorator, `@xun.make_shared`, that can make many functions serializable.

## Function Scope and Best Practices

 * You should only reference global scope from a function that would not change the outcome of the function if changed. Global scope is not considered when identifying results, thus changes to the global scope might give undesired results.
 * A good use for global scope is to specify configuration values, such as cluster addresses or file system paths.
    ```python
    data_dir = '/path/to/data'

    @xun.function()
    def load_data():
        return load(data_dir)
    ```
 * If you want a variable change to impact your results, define it as a xun function. For example to configure a simulation with a fixed seed, define the value as a xun function rather than a variable in global scope
     ```python
     @xun.function()
     def simulation_seed():
         return 196883
     ```

## Yielding Auxiliary Results

Functions can yield auxiliary results accessible through interfaces. This is useful if a function returns large, but separable results. Results can be yielded to interfaces specified by a decorator `@<xun.Function>.interface`. This let's the original function write results accessible through the interface as if they were xun functions. Yields from a xun function are declared in the function body as yield statements of the form `yield <call-to-interface> is <expr>`.

Interfaces must specify which function that should be responsible for producing it's result.

In this example the function `f` returns what is passed to it, but in addition yields results to interfaces `even` and `odd`. Calling `even` and `odd` interfaces will return the `n-th` even and odd integer respectively.

```python
import xun


@xun.function()
def f(n):
    yield even(n) is n * 2
    yield odd(n) is n * 2 + 1
    return n


@f.interface
def even(n):
    yield from f(n)


@f.interface
def odd(n):
    yield from f(n)
```
