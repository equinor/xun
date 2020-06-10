from datetime import datetime
from pytz import utc
import argparse
import json
import re
import sys


# thanks stackoverflow
# https://stackoverflow.com/questions/25470844/specify-format-for-input-arguments-argparse-python
def valid_date(s):
    date_fmts = ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f')
    for fmt in date_fmts:
        try:
            time = datetime.strptime(s, fmt)
            return utc.localize(time)
        except ValueError:
            pass

    msg = 'Invalid date: {}. Supported formats:\n\t'
    msg += '\n\t'.join(date_fmts)
    raise argparse.ArgumentTypeError(msg)


def struct_fmt(s):
    reg = re.compile(r'^([\<\>\@\=\!]?([1-9][0-9]*)?[b\?ilfdsp])*')
    res = re.fullmatch(reg, s)
    if res:
        return s
    else:
        msg = '''Not a valid format: "{}". Expected types b?ilfdsp'''.format(s)
        raise ValueError(msg)


def schema_action(func):
    class schema_action_internal(argparse.Action):
        def __init__(self, option_strings, dest=None, nargs=None):
            (super(schema_action_internal, self)
            .__init__(option_strings, dest, nargs=0)
            )
        def __call__(self, parser, namespace, values, option_string=None):
            schema = func(namespace)
            print(json.dumps(schema))
            sys.exit(0)
    return schema_action_internal
