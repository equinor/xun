"""
This module file is the entrypoint in case the project package is run with
`python -m {{cookiecutter.module_name}}`.
For more info, read:
    - https://docs.python.org/3/using/cmdline.html#cmdoption-m
"""

from .{{cookiecutter.module_name}} import capitalize
import argparse
import logging
import xun


logging.basicConfig(level=logging.WARNING)
logging.getLogger('xun').setLevel(logging.DEBUG)


driver = xun.functions.driver.Sequential()
store = xun.functions.store.Memory()


def main():
    """
    If this workflow is to be executable, this is where the setup for the
    driver and the store should go, along with the entrypoint function(s).
    """

    @xun.function()
    def entry_point_workflow(name):
        print(f'Hello {capitalized_name}')
        with ...:
            """Set up your workflow here"""
            capitalized_name = capitalize(name)

    entry_point_workflow.blueprint("world").run(driver=driver, store=store)


if __name__ == '__main__':
    main()
