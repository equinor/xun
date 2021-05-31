from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from datetime import datetime
from datetime import timedelta


class Identity:
    def __init__(self, key, cert):
        self.key = key
        self.cert = cert

        self.private_key = self.key
        self.public_key = self.private_key.public_key()

    @property
    def private_key_bytes(self):
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @property
    def public_key_bytes(self):
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    @property
    def cert_bytes(self):
        return self.cert.public_bytes(serialization.Encoding.PEM)


def create_certificate_authority(common_name='xun-private-ca'):
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    xun_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    )

    now = datetime.utcnow()

    ca_cert = (x509.CertificateBuilder()
        .subject_name(xun_name)
        .issuer_name(xun_name)

        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())

        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]),
            critical=False)
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True)
        .add_extension(
            x509.KeyUsage(digital_signature=False,
                          content_commitment=False,
                          key_encipherment=False,
                          data_encipherment=False,
                          key_agreement=False,
                          key_cert_sign=True,
                          crl_sign=True,
                          encipher_only=False,
                          decipher_only=False),
            critical=True)

        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=60))

        .sign(ca_key, hashes.SHA256())
    )

    return Identity(key=ca_key, cert=ca_cert)


def create_client(common_name, ca):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    )
    issuer_name = x509.Name(
        ca.cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    )

    now = datetime.utcnow()

    cert = (x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_name)

        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())

        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True)

        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=60))

        .sign(ca.key, hashes.SHA256())
    )

    return Identity(key=key, cert=cert)
