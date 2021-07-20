from .crypto import create_certificate_authority
from .crypto import create_client
from functools import partial
import contextlib
import os


# Pyyaml has this awkward interface where you need to specify a loader
from yaml import load as _load_yaml
from yaml import dump as _dump_yaml
try:
    from yaml import CLoader as _yaml_Loader
except ImportError:
    from yaml import Loader as _yaml_Loader


def load_yaml(filename):
    with open(filename, 'r') as f:
        return _load_yaml(f, Loader=_yaml_Loader)


def dump_yaml(obj, filename):
    with open(filename, 'w') as f:
        _dump_yaml(obj, f)


def create_tls_identities(args):
    path = args.path
    path.mkdir(exist_ok=True, parents=True)

    def secure_opener(path, flags):
        return os.open(path, flags, 0o600)

    s_open_wb = partial(open, mode='wb', opener=secure_opener)

    def dump(name, constructor):
        identity = constructor(name)

        identity.private_key_path = str(path / f'{name}-private-key.pem')
        identity.public_key_path = str(path / f'{name}-public-key.pem')
        identity.cert_path = str(path / f'{name}-cert.pem')


        with contextlib.ExitStack() as exit_stack:
            private_key_file = (
                exit_stack.enter_context(s_open_wb(identity.private_key_path))
            )
            public_key_file = (
                exit_stack.enter_context(s_open_wb(identity.public_key_path))
            )
            cert_file = (
                exit_stack.enter_context(s_open_wb(identity.cert_path))
            )

            private_key_file.write(identity.private_key_bytes)
            public_key_file.write(identity.public_key_bytes)
            cert_file.write(identity.cert_bytes)

        return identity

    ca = dump('xun-private-ca', create_certificate_authority)
    client = dump('xun-dask-client', partial(create_client, ca=ca))
    scheduler = dump('xun-dask-scheduler', partial(create_client, ca=ca))
    worker = dump('xun-dask-worker', partial(create_client, ca=ca))

    if not args.no_dask:
        update_config({
            'distributed': {
                'comm': {
                    'require-encryption': True,
                    'tls': {
                        'ca-file': ca.cert_path,
                        'client': {
                            'key': client.private_key_path,
                            'cert': client.cert_path,
                        },
                        'scheduler': {
                            'key': scheduler.private_key_path,
                            'cert': scheduler.cert_path,
                        },
                        'worker': {
                            'key': worker.private_key_path,
                            'cert': worker.cert_path,
                        },
                    }
                },
            },
        }, args.dask_config_path)


def update_config(config, path):
    path.parent.mkdir(exist_ok=True, parents=True)

    if path.exists():
        old_config = load_yaml(path) or {}
        old_config.update(config)
        config = old_config

    dump_yaml(config, path)
