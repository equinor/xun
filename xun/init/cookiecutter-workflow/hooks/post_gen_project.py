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
    remove_filepath = os.path.join(os.getcwd(), '__main__.py')
    if os.path.isfile(remove_filepath):
        os.remove(remove_filepath)
