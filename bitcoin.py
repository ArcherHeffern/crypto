from dataclasses import dataclass, field
from hashlib import sha256
from random import choice, randint
from typing import Generator, Optional
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import crypto


@dataclass
class TransactionLog:
    log: list[Transaction] = field(default_factory=list)

    def append_transaction(
        self, sender: crypto.PublicKeys, reciever: crypto.PublicKeys, amount: int
    ):
        previous_transaction_hash = (
            self.log[len(self.log) - 2].get_hash() if len(self.log) != 0 else b""
        )

        transaction = Transaction(previous_transaction_hash, sender, reciever, amount)
        self.log.append(transaction)


@dataclass
class Transaction:
    previous_transaction_hash: bytes
    sender: crypto.PublicKeys
    reciever: crypto.PublicKeys
    amount: int

    def get_signature(self, priv: crypto.SigningPrivateKey) -> crypto.Signature:
        return crypto.sign(self.as_bytes(), priv)

    def get_hash(self) -> bytes:
        return sha256(self.as_bytes()).digest()

    def as_bytes(self) -> bytes:
        b = bytearray()
        b += self.previous_transaction_hash
        b += self._public_keys_to_bytes(self.sender)
        b += self._public_keys_to_bytes(self.reciever)
        b += self.amount.to_bytes()
        return b

    @staticmethod
    def _public_keys_to_bytes(public_keys: crypto.PublicKeys):
        return public_keys.encryption_key.public_bytes(
            Encoding.DER, PublicFormat.PKCS1
        ) + public_keys.signing_key.public_bytes(Encoding.DER, PublicFormat.PKCS1)


@dataclass
class Block:
    prev_hash: bytes
    transactions: TransactionLog
    nonce: Optional[int] = None
    required_work: int = (
        2  # This is number of bytes needed to be 0. Multiply by 4 for bits.
    )

    def get_hash(self) -> Optional[bytes]:
        if self.nonce is None:
            return None
        b = bytearray()
        for transaction in self.transactions.log:
            b += transaction.as_bytes()
        b += str(self.nonce).encode()
        return sha256(b).digest()

    def try_compute_nonce(self) -> Generator[Optional[int], None, None]:
        if self.nonce is not None:
            yield self.nonce
            return
        b = bytearray()
        for transaction in self.transactions.log:
            b += transaction.as_bytes()
        nonce = 1
        while True:
            if nonce % 1_000_000 == 0:
                yield None
                print(nonce)
            h = sha256(b + str(nonce).encode()).digest()
            for i in range(self.required_work):
                if h[i] != 0:
                    break
            else:
                self.nonce = nonce
                yield nonce
                return
            nonce += 1


if __name__ == "__main__":
    people = [crypto.Person.create() for _ in range(10)]
    transactions = TransactionLog()
    print("Creating Transactions")
    for _ in range(10):
        transactions.append_transaction(
            choice(people).get_public_keys(),
            choice(people).get_public_keys(),
            randint(0, 100),
        )
    print("Computing Nonce")
    block = Block(b"", transactions)
    nonce = None
    for nonce in block.try_compute_nonce():
        ...
    print(nonce)
    print(block.get_hash())
