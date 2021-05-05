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


from . import functions
from . import sima
from . import init
from .cli_helpers import schema_action
from .cli_helpers import valid_date
from .cli_helpers import struct_fmt


def main(args=None):
    args = parser.parse_args(args=args)

    if 'func' not in args:
        parser.print_help()
        sys.exit(1)

    args.func(args)


parser = argparse.ArgumentParser(description=None)
subparsers = parser.add_subparsers()


#
# Sima result export command
#
parser_export = subparsers.add_parser('sima-export')
parser_export.set_defaults(func=sima.export.main)
parser_export.add_argument('format',
                            help='python struct based format',
                            type=struct_fmt)
parser_export.add_argument('bin_input')
parser_export.add_argument('-o',
                            '--output',
                            default=None)
parser_export.add_argument('-s', '--out-schema',
                           action=schema_action(
                               lambda args: sima.export.schema(args.format)
                           ))


#
# Xun functions
#

parser_fgraph = subparsers.add_parser('graph')
parser_fgraph.set_defaults(func=functions.cli.xun_graph)
parser_fgraph.add_argument('module')
parser_fgraph.add_argument('call_string')
parser_fgraph_action = parser_fgraph.add_mutually_exclusive_group()
parser_fgraph_action.add_argument('--list-layout',
                                  action='store_true',
                                  default=True)
parser_fgraph_action.add_argument('--dot-layout', action='store_true')
parser_fgraph_action.add_argument('--dot', action='store_true')


#
# create new project from cookiecutter template
#
parser_template = subparsers.add_parser('init')
parser_template.set_defaults(func=init.cli.main)
parser_template.add_argument('--path',
                             help='where to output the generated project',
                             default='.')
