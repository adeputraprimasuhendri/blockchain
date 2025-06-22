import hashlib
import time
import uuid


class Transaction:
    def __init__(self, sender, recipient, amount, fee=0):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.fee = fee
        self.timestamp = time.time()
        self.signature = None

    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount,
            'fee': self.fee,
            'timestamp': self.timestamp,
            'signature': self.signature
        }

    def sign_transaction(self, private_key=None):
        # Simplified signing - in production use proper cryptographic signatures
        tx_string = f"{self.sender}{self.recipient}{self.amount}{self.timestamp}"
        self.signature = hashlib.sha256(tx_string.encode()).hexdigest()

