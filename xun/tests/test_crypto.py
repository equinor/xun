from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.x509 import load_pem_x509_certificate
from xun.infrastructure.crypto import create_certificate_authority
from xun.infrastructure.crypto import create_client


def test_certificate_authority():
    ca = create_certificate_authority()
    ca.public_key.verify(ca.cert.signature, ca.cert.tbs_certificate_bytes)


def test_create_client():
    ca = create_certificate_authority()
    client = create_client('client-name', ca)
    ca.public_key.verify(client.cert.signature,
                         client.cert.tbs_certificate_bytes)


def test_serialization():
    ca = create_certificate_authority()

    private_key = load_pem_private_key(ca.private_key_bytes, None)
    public_key = load_pem_public_key(ca.public_key_bytes)
    cert = load_pem_x509_certificate(ca.cert_bytes)

    public_key.verify(cert.signature, cert.tbs_certificate_bytes)
    assert cert.signature == private_key.sign(cert.tbs_certificate_bytes)
