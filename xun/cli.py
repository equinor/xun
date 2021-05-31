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
from pathlib import Path
import argparse
import sys


from . import functions
from . import infrastructure
from . import init


def main(args=None):
    args = parser.parse_args(args=args)

    if 'func' not in args:
        parser.print_help()
        sys.exit(1)

    args.func(args)


parser = argparse.ArgumentParser(description=None)
subparsers = parser.add_subparsers()


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


#
# Dask crypto identities
#
parser_crypto = subparsers.add_parser('create-cryptographic-identities')
parser_crypto.set_defaults(func=infrastructure.cli.create_tls_identities)
parser_crypto.add_argument('--path',
                           help='target directory',
                           default=Path.home() / '.xun/crypto',
                           type=Path)
parser_crypto.add_argument('--dask-config-path',
                           help='root directory for dask config',
                           default=Path.home() / '.config/dask/xun-tls.yml',
                           type=Path)
parser_crypto.add_argument('--no-dask',
                           help='Suppress the creation of dask config file',
                           action='store_true')
