import hashlib


class ExportError(Exception): pass
class SchemaError(Exception): pass


def args_hash(args):
    args = vars(args)
    strings = sorted('{}={}'.format(k, v) for k, v in args.items())
    param_str = ','.join(strings)

    return hashlib.sha256(param_str.encode('utf-8')).hexdigest()


def filename_from_args(args, prefix='', postfix=''):
    hash = args_hash(args)
    return prefix + hash + postfix
