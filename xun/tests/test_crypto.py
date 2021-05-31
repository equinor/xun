from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.x509 import load_pem_x509_certificate
from dask.distributed import Security
from xun.cli import parser_crypto as crypto_arg_parse
from xun.infrastructure.cli import create_tls_identities
from xun.infrastructure.crypto import create_certificate_authority
from xun.infrastructure.crypto import create_client
import dask


def test_certificate_authority():
    ca = create_certificate_authority()
    ca.public_key.verify(ca.cert.signature,
                         ca.cert.tbs_certificate_bytes,
                         padding.PKCS1v15(),
                         ca.cert.signature_hash_algorithm)


def test_create_client():
    ca = create_certificate_authority()
    client = create_client('client-name', ca)
    ca.public_key.verify(client.cert.signature,
                         client.cert.tbs_certificate_bytes,
                         padding.PKCS1v15(),
                         client.cert.signature_hash_algorithm)


def test_serialization():
    ca = create_certificate_authority()

    private_key = load_pem_private_key(ca.private_key_bytes, None)
    public_key = load_pem_public_key(ca.public_key_bytes)
    cert = load_pem_x509_certificate(ca.cert_bytes)

    public_key.verify(cert.signature,
                      cert.tbs_certificate_bytes,
                      padding.PKCS1v15(),
                      cert.signature_hash_algorithm)
    assert cert.signature == private_key.sign(cert.tbs_certificate_bytes,
                                              padding.PKCS1v15(),
                                              cert.signature_hash_algorithm)


def test_dask_tls(tmpdir):
    args = crypto_arg_parse.parse_args([
        '--path', str(tmpdir),
        '--dask-config-path', str(tmpdir.join('xun-tls.yml')),
    ])

    create_tls_identities(args)

    assert tmpdir.join('xun-private-ca-private-key.pem').check()
    assert tmpdir.join('xun-private-ca-public-key.pem').check()
    assert tmpdir.join('xun-private-ca-cert.pem').check()
    assert tmpdir.join('xun-dask-client-private-key.pem').check()
    assert tmpdir.join('xun-dask-client-public-key.pem').check()
    assert tmpdir.join('xun-dask-client-cert.pem').check()
    assert tmpdir.join('xun-dask-scheduler-private-key.pem').check()
    assert tmpdir.join('xun-dask-scheduler-public-key.pem').check()
    assert tmpdir.join('xun-dask-scheduler-cert.pem').check()
    assert tmpdir.join('xun-dask-worker-private-key.pem').check()
    assert tmpdir.join('xun-dask-worker-public-key.pem').check()
    assert tmpdir.join('xun-dask-worker-cert.pem').check()
    assert tmpdir.join('xun-tls.yml').check()

    cfg = dask.config.collect([f'{str(tmpdir)}/xun-tls.yml'])
    dask.config.update(dask.config.config, cfg)
    sec = Security()
    assert sec.tls_ca_file == str(tmpdir.join('xun-private-ca-cert.pem'))
    assert sec.tls_client_key == str(tmpdir.join('xun-dask-client-private-key.pem'))
    assert sec.tls_client_cert == str(tmpdir.join('xun-dask-client-cert.pem'))
    assert sec.tls_scheduler_key == str(tmpdir.join('xun-dask-scheduler-private-key.pem'))
    assert sec.tls_scheduler_cert == str(tmpdir.join('xun-dask-scheduler-cert.pem'))
    assert sec.tls_worker_key == str(tmpdir.join('xun-dask-worker-private-key.pem'))
    assert sec.tls_worker_cert == str(tmpdir.join('xun-dask-worker-cert.pem'))
