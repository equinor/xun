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


from . import sima
from . import zephyre
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
# zephyre command
#
parser_zephyre = subparsers.add_parser('zephyre')
parser_zephyre.set_defaults(func=zephyre.main)
parser_zephyre.add_argument('measurement_name',
                            help='Name of the measurement to download')
parser_zephyre.add_argument('start_time',
                            help='The start date in format YYYY-MM-DD or '
                                 'YYYY-MM-DDTHH:mm:ss',
                            type=valid_date)
parser_zephyre.add_argument('end_time',
                            help='The end date in format YYYY-MM-DD or '
                                 'YYYY-MM-DDTHH:mm:ss or '
                                 'YYYY-MM-DDTHH:mm:ss.ffffff',
                            type=valid_date)
parser_zephyre.add_argument('-o',
                            '--output',
                            default=None)
parser_zephyre.add_argument('-s', '--out-schema',
                            # help='Print the schema of the output file',
                            action=schema_action(
                                lambda _: zephyre.schema()
                            ))


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
