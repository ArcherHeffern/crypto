from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from typing import NamedTuple, NewType, Optional
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

EncryptionPrivateKey = NewType("EncryptionPrivateKey", RSAPrivateKey)
EncryptionPublicKey = NewType("EncryptionPublicKey", RSAPublicKey)
SigningPrivateKey = NewType("SigningPrivateKey", RSAPrivateKey)
SigningPublicKey = NewType("SigningPublicKey", RSAPublicKey)
Signature = NewType("Signature", bytes)
CipherText = NewType("CipherText", bytes)


class EncryptionKeys(NamedTuple):
    pub: EncryptionPublicKey
    priv: EncryptionPrivateKey


class SigningKeys(NamedTuple):
    pub: SigningPublicKey
    priv: SigningPrivateKey


class PublicKeys(NamedTuple):
    encryption_key: EncryptionPublicKey
    signing_key: SigningPublicKey


@dataclass
class Person:
    encryption_keys: EncryptionKeys
    signing_keys: SigningKeys

    @staticmethod
    def create() -> Person:
        return Person(create_key_pair_for_encryption(), create_key_pair_for_signing())

    def get_public_keys(self) -> PublicKeys:
        return PublicKeys(self.encryption_keys.pub, self.signing_keys.pub)


def create_key_pair_for_encryption() -> EncryptionKeys:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return EncryptionKeys(
        EncryptionPublicKey(private_key.public_key()), EncryptionPrivateKey(private_key)
    )


def create_key_pair_for_signing() -> SigningKeys:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return SigningKeys(
        SigningPublicKey(private_key.public_key()), SigningPrivateKey(private_key)
    )


def sign(message: bytes, private_key: SigningPrivateKey) -> Signature:
    return Signature(
        private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )
    )


def verify(signature: Signature, message: bytes, public_key: SigningPublicKey) -> bool:
    try:
        public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )
        return True
    except InvalidSignature:
        return False


def encrypt(message: bytes, public_key: EncryptionPublicKey) -> CipherText:
    return CipherText(
        public_key.encrypt(
            (message * 2),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    )


def decrypt(ciphertext: CipherText, private_key: EncryptionPrivateKey) -> Optional[str]:
    msg = private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    if len(msg) % 2 != 0:
        return None

    first_half = msg[0 : len(msg) // 2]
    second_half = msg[len(msg) // 2 :]
    if first_half != second_half:
        return None
    return first_half.decode()
