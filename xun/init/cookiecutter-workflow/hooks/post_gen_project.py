"""
This post-generate hook removes the __main__.py file if the project is not
supposed to be runnable.
"""
import os

make_runnable = '{{cookiecutter.make_runnable}}' in [
    'y',
    'yes',
    'True',
    'true',
    '1',
]

if not make_runnable:
    for path in (
        os.path.join(os.getcwd(), '__main__.py'),
        os.path.join(os.getcwd(), '{{cookiecutter.module_name}}.ipynb'),
    ):
        if os.path.isfile(path):
            os.remove(path)
