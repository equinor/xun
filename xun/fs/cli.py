import argparse
import base64
import pickle


def main(args):
    from .filesystem import fuse, Fuse, XunFS
    server = XunFS(args.store,
                   args.query,
                   usage="XunFS\n" + Fuse.fusage,
                   version="%prog " + fuse.__version__)
    fuse_args = list(args.fuse_args)[1:]  # Strip -- from previous parse
    fuse_args.append('-f')  # Run in foreground
    server.parse(fuse_args)
    server.main()


class StoreAction(argparse.Action):
    class StoreConstructors:
        @staticmethod
        def disk(path):
            from ..functions.store import Disk
            return Disk(path, create_dirs=False)

    def __call__(self, parser, namespace, values, option_string=None):
        store_name, *args = values
        try:
            store = getattr(StoreAction.StoreConstructors, store_name)(*args)
            setattr(namespace, self.dest, store)
        except Exception as e:
            parser.error(f'Invalid store ({store_name}) arguments ({args})')


class QueryAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, ' '.join(values))


def store_pickle(s):
    return pickle.loads(base64.urlsafe_b64decode(s.encode()))


def query_file(filename):
    with open(filename, 'r') as f:
        return f.read()
