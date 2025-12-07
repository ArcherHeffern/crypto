from dataclasses import dataclass, field
from hashlib import sha256
from pprint import pprint
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from random import choice, randint
import crypto


@dataclass
class TransactionLog:
    log: list[Transaction] = field(default_factory=list)

    def append_transaction(
        self, sender: crypto.Person, reciever_pub_keys: crypto.PublicKeys, amount: int
    ):
        previous_transaction = (
            self.log[len(self.log) - 2].to_bytes() if len(self.log) != 0 else b""
        )
        previous_transaction_hash = sha256(previous_transaction).digest()
        previous_transaction_hash_signed = crypto.sign(
            previous_transaction_hash, sender.signing_keys.priv
        )

        next_owner_public_keys = reciever_pub_keys.encryption_key.public_bytes(
            Encoding.DER, PublicFormat.PKCS1
        ) + reciever_pub_keys.signing_key.public_bytes(Encoding.DER, PublicFormat.PKCS1)
        next_owner_public_keys_signed = crypto.sign(
            next_owner_public_keys, sender.signing_keys.priv
        )

        transaction = Transaction(
            previous_transaction_hash_signed, next_owner_public_keys_signed, amount
        )
        self.log.append(transaction)


@dataclass
class Transaction:
    previous_transaction_hash_signed: crypto.Signature = field(repr=False)
    next_owners_public_key_signed: crypto.Signature = field(repr=False)
    amount: int

    def to_bytes(self) -> bytes:
        return (
            self.previous_transaction_hash_signed + self.next_owners_public_key_signed
        )

    def to_string(self) -> str:
        return self.to_bytes().decode()


if __name__ == "__main__":
    people = [crypto.Person.create() for _ in range(10)]
    transaction_log = TransactionLog()
    for _ in range(10):
        transaction_log.append_transaction(choice(people), choice(people).get_public_keys(), randint(0, 100))
    pprint(transaction_log)
