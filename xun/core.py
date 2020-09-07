import hashlib


class ExportError(Exception): pass
class SchemaError(Exception): pass


def args_hash(args):
    """Hash command line arguments

    Converts full command line arguments to a hash to use as filename

    Parameters
    ----------
    args : argparse.Namespace
        The argument namespace as parsed by argparse

    Returns
    -------
    str
        Hash digest value as a string of hexadecimal digits
    """
    args = vars(args)
    strings = sorted('{}={}'.format(k, v) for k, v in args.items())
    param_str = ','.join(strings)

    return hashlib.sha256(param_str.encode('utf-8')).hexdigest()


def filename_from_args(args, prefix='', postfix=''):
    """Filename from command line arguments

    Parameters
    ----------
    args : argparse.Namespace
        The argument namespace as parsed by argparse
    prefix : str, optional
        Prefix of the file name
    postfix : str, optional
        Postfix of the file name

    Returns
    -------
    str
        File name

    Examples
    --------

    >>> filename_from_args(args, prefix='prefix', postfix='.txt')
    'prefixe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.txt'

    """
    hash = args_hash(args)
    return prefix + hash + postfix
