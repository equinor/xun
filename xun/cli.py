"""
Module that contains the command line app.

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will
  cause problems: the code will get executed twice:

  - When you run `python -m xun` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``xun.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``xun.__main__`` in ``sys.modules``.

  Also see (1) from http://click.pocoo.org/5/setuptools/#setuptools-integration
"""
import argparse
import sys
import re
from pathlib import Path


from xun.sima import cmd_extract


def valid_format(s):
    reg = re.compile(r'^([\<\>\@\=\!]?([1-9][0-9]*)?[b\?ilfdsp])*')
    res = re.fullmatch(reg, s)
    if res:
        return s
    else:
        msg = '''Not a valid format: "{}". Expected types b?ilfdsp'''.format(s)
        raise ValueError(msg)


def valid_file_path(p):
    path = Path(p)
    if path.exists() and path.is_file():
        return path
    else:
        msg = 'Not a valid path to a file: "{0}".'.format(p)
        raise ValueError(msg)


parser = argparse.ArgumentParser(description=None)
subparsers = parser.add_subparsers(title='sima')


#
# Extract command
#
parser_extract = subparsers.add_parser('extract')
parser_extract.add_argument('format',
                        help='python struct based format',
                        type=valid_format)
group = parser_extract.add_mutually_exclusive_group(required=True)
group.add_argument('-bi', '--bin_input',
                        type=valid_file_path)
group.add_argument('-os', '--out-schema',
                        action='store_true')
parser_extract.add_argument('-o',
                        '--output',
                        required=True)
parser_extract.set_defaults(func=cmd_extract)


def main(args=None):
    args = parser.parse_args(args=args)

    if 'func' not in args:
        parser.print_help()
        sys.exit(1)
