class Portfolio:
    def __init__(self, blockchain):
        self.blockchain = blockchain

    def get_balance(self, address):
        balance = 0
        for block in self.blockchain.chain:
            for transaction in block.transactions:
                if transaction.sender == address:
                    balance -= (transaction.amount + transaction.fee)
                if transaction.recipient == address:
                    balance += transaction.amount
            # Mining reward
            if block.miner_address == address:
                balance += self.blockchain.mining_reward
        return balance

    def get_transaction_history(self, address):
        history = []
        for block in self.blockchain.chain:
            for transaction in block.transactions:
                if transaction.sender == address or transaction.recipient == address:
                    tx_data = transaction.to_dict()
                    tx_data['block_index'] = block.index
                    tx_data['block_hash'] = block.hash
                    history.append(tx_data)
        return history

    def get_portfolio_summary(self, address):
        balance = self.get_balance(address)
        history = self.get_transaction_history(address)
        sent_count = len([tx for tx in history if tx['sender'] == address])
        received_count = len([tx for tx in history if tx['recipient'] == address])

        return {
            'address': address,
            'balance': balance,
            'total_transactions': len(history),
            'sent_transactions': sent_count,
            'received_transactions': received_count,
            'transaction_history': history
        }
