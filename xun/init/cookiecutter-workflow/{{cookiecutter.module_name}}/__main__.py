"""
This module file is the entrypoint in case the project package is run with
`python -m {{cookiecutter.module_name}}`.
For more info, read:
    - https://docs.python.org/3/using/cmdline.html#cmdoption-m
"""

from nbconvert.preprocessors import ExecutePreprocessor
import logging
import nbformat
import xun


logging.basicConfig(level=logging.WARNING)
logging.getLogger('xun').setLevel(logging.DEBUG)


driver = xun.functions.driver.Sequential()
store = xun.functions.store.Memory()


def main():
    """
    If this workflow is to be executable, the
    {{cookiecutter.module_name}}.ipynb notebook is executed from here and the
    executed notebook is then stored in executed_notebook.ipynb.
    """

    with open('{{cookiecutter.module_name}}/{{cookiecutter.module_name}}.ipynb') as f:
        nb = nbformat.read(f, as_version=4)

    ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
    ep.preprocess(nb, {'metadata': {'path': '{{cookiecutter.module_name}}/'}})

    with open('{{cookiecutter.module_name}}/executed_notebook.ipynb',
              'w',
              encoding='utf-8') as f:
        nbformat.write(nb, f)


if __name__ == '__main__':
    main()
