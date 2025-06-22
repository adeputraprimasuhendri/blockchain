import hashlib
import json
import time
import threading
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import socket
import uuid
from urllib.parse import urlparse


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


class Block:
    def __init__(self, index, transactions, previous_hash, miner_address):
        self.index = index
        self.timestamp = time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.miner_address = miner_address
        self.nonce = 0
        self.hash = None
        self.merkle_root = self.calculate_merkle_root()

    def calculate_merkle_root(self):
        if not self.transactions:
            return "0"
        tx_hashes = [hashlib.sha256(json.dumps(tx.to_dict()).encode()).hexdigest()
                     for tx in self.transactions]
        while len(tx_hashes) > 1:
            if len(tx_hashes) % 2 != 0:
                tx_hashes.append(tx_hashes[-1])
            tx_hashes = [hashlib.sha256((tx_hashes[i] + tx_hashes[i + 1]).encode()).hexdigest()
                         for i in range(0, len(tx_hashes), 2)]
        return tx_hashes[0]

    def calculate_hash(self):
        block_string = f"{self.index}{self.timestamp}{self.previous_hash}{self.merkle_root}{self.nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty=4):
        target = "0" * difficulty
        while self.hash is None or not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()
        print(f"Block mined: {self.hash}")

    def to_dict(self):
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'transactions': [tx.to_dict() for tx in self.transactions],
            'previous_hash': self.previous_hash,
            'miner_address': self.miner_address,
            'nonce': self.nonce,
            'hash': self.hash,
            'merkle_root': self.merkle_root
        }


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


class Blockchain:
    def __init__(self, node_id):
        self.chain = [self.create_genesis_block()]
        self.difficulty = 4
        self.pending_transactions = []
        self.mining_reward = 10
        self.node_id = node_id
        self.nodes = set()
        self.portfolio = Portfolio(self)

    def create_genesis_block(self):
        genesis_transactions = []
        genesis_block = Block(0, genesis_transactions, "0", "genesis")
        genesis_block.hash = genesis_block.calculate_hash()
        return genesis_block

    def get_latest_block(self):
        return self.chain[-1]

    def add_transaction(self, transaction):
        if self.validate_transaction(transaction):
            transaction.sign_transaction()
            self.pending_transactions.append(transaction)
            return True
        return False

    def validate_transaction(self, transaction):
        if transaction.sender == transaction.recipient:
            return False
        if transaction.amount <= 0:
            return False
        if transaction.sender != "genesis":  # Skip validation for genesis transactions
            sender_balance = self.portfolio.get_balance(transaction.sender)
            if sender_balance < (transaction.amount + transaction.fee):
                return False
        return True

    def mine_pending_transactions(self, mining_reward_address):
        # Add mining reward transaction
        reward_transaction = Transaction("genesis", mining_reward_address, self.mining_reward)
        reward_transaction.sign_transaction()

        transactions_to_mine = self.pending_transactions + [reward_transaction]

        block = Block(
            len(self.chain),
            transactions_to_mine,
            self.get_latest_block().hash,
            mining_reward_address
        )

        block.mine_block(self.difficulty)
        self.chain.append(block)
        self.pending_transactions = []

        print(f"Block successfully mined by {mining_reward_address}")
        return block

    def validate_chain(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            if current_block.hash != current_block.calculate_hash():
                return False

            if current_block.previous_hash != previous_block.hash:
                return False

        return True

    def replace_chain(self, new_chain):
        if len(new_chain) > len(self.chain) and self.validate_imported_chain(new_chain):
            self.chain = new_chain
            return True
        return False

    def validate_imported_chain(self, chain):
        # Convert dict chain to Block objects if needed
        if isinstance(chain[0], dict):
            chain = self.dict_chain_to_objects(chain)

        for i in range(1, len(chain)):
            current_block = chain[i]
            previous_block = chain[i - 1]

            if current_block.hash != current_block.calculate_hash():
                return False

            if current_block.previous_hash != previous_block.hash:
                return False

        return True

    def dict_chain_to_objects(self, dict_chain):
        object_chain = []
        for block_dict in dict_chain:
            transactions = []
            for tx_dict in block_dict['transactions']:
                tx = Transaction(tx_dict['sender'], tx_dict['recipient'], tx_dict['amount'], tx_dict['fee'])
                tx.id = tx_dict['id']
                tx.timestamp = tx_dict['timestamp']
                tx.signature = tx_dict['signature']
                transactions.append(tx)

            block = Block(block_dict['index'], transactions, block_dict['previous_hash'], block_dict['miner_address'])
            block.timestamp = block_dict['timestamp']
            block.nonce = block_dict['nonce']
            block.hash = block_dict['hash']
            block.merkle_root = block_dict['merkle_root']
            object_chain.append(block)

        return object_chain

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def to_dict(self):
        return {
            'chain': [block.to_dict() for block in self.chain],
            'pending_transactions': [tx.to_dict() for tx in self.pending_transactions],
            'difficulty': self.difficulty,
            'mining_reward': self.mining_reward,
            'node_id': self.node_id
        }


class BlockchainNode:
    def __init__(self, host='localhost', port=5000):
        self.blockchain = Blockchain(f"{host}:{port}")
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.setup_routes()
        self.sync_timer = None
        self.mining_thread = None
        self.auto_mining = False

    def setup_routes(self):
        @self.app.route('/mine', methods=['POST'])
        def mine():
            data = request.get_json()
            miner_address = data.get('miner_address', f'miner_{self.port}')

            if not self.blockchain.pending_transactions:
                return jsonify({'message': 'No pending transactions to mine'}), 400

            block = self.blockchain.mine_pending_transactions(miner_address)

            # Broadcast new block to other nodes
            self.broadcast_block(block)

            return jsonify({
                'message': 'Block mined successfully',
                'block': block.to_dict()
            })

        @self.app.route('/transactions/new', methods=['POST'])
        def new_transaction():
            data = request.get_json()

            required_fields = ['sender', 'recipient', 'amount']
            if not all(field in data for field in required_fields):
                return jsonify({'message': 'Missing required fields'}), 400

            transaction = Transaction(
                data['sender'],
                data['recipient'],
                data['amount'],
                data.get('fee', 0)
            )

            if self.blockchain.add_transaction(transaction):
                # Broadcast transaction to other nodes
                self.broadcast_transaction(transaction)

                return jsonify({
                    'message': 'Transaction added successfully',
                    'transaction': transaction.to_dict()
                })
            else:
                return jsonify({'message': 'Invalid transaction'}), 400

        @self.app.route('/chain', methods=['GET'])
        def get_chain():
            return jsonify(self.blockchain.to_dict())

        @self.app.route('/portfolio/<address>', methods=['GET'])
        def get_portfolio(address):
            portfolio = self.blockchain.portfolio.get_portfolio_summary(address)
            return jsonify(portfolio)

        @self.app.route('/balance/<address>', methods=['GET'])
        def get_balance(address):
            balance = self.blockchain.portfolio.get_balance(address)
            return jsonify({'address': address, 'balance': balance})

        @self.app.route('/nodes/register', methods=['POST'])
        def register_nodes():
            data = request.get_json()
            nodes = data.get('nodes')

            if nodes is None:
                return jsonify({'message': 'No nodes provided'}), 400

            for node in nodes:
                self.blockchain.register_node(node)

            return jsonify({
                'message': 'Nodes registered successfully',
                'total_nodes': list(self.blockchain.nodes)
            })

        @self.app.route('/nodes/resolve', methods=['GET'])
        def consensus():
            replaced = self.resolve_conflicts()

            if replaced:
                response = {
                    'message': 'Chain was replaced',
                    'new_chain': [block.to_dict() for block in self.blockchain.chain]
                }
            else:
                response = {
                    'message': 'Chain is authoritative',
                    'chain': [block.to_dict() for block in self.blockchain.chain]
                }

            return jsonify(response)

        @self.app.route('/sync', methods=['POST'])
        def sync_chain():
            data = request.get_json()
            new_chain = data.get('chain')

            if new_chain and self.blockchain.replace_chain(new_chain):
                return jsonify({'message': 'Chain synchronized successfully'})
            else:
                return jsonify({'message': 'Chain sync failed or not needed'})

        @self.app.route('/broadcast/transaction', methods=['POST'])
        def receive_transaction():
            data = request.get_json()

            transaction = Transaction(
                data['sender'],
                data['recipient'],
                data['amount'],
                data.get('fee', 0)
            )
            transaction.id = data['id']
            transaction.timestamp = data['timestamp']
            transaction.signature = data['signature']

            if self.blockchain.add_transaction(transaction):
                return jsonify({'message': 'Transaction received'})
            else:
                return jsonify({'message': 'Invalid transaction'}), 400

        @self.app.route('/broadcast/block', methods=['POST'])
        def receive_block():
            data = request.get_json()

            # Validate and add block
            block_transactions = []
            for tx_data in data['transactions']:
                tx = Transaction(tx_data['sender'], tx_data['recipient'],
                                 tx_data['amount'], tx_data['fee'])
                tx.id = tx_data['id']
                tx.timestamp = tx_data['timestamp']
                tx.signature = tx_data['signature']
                block_transactions.append(tx)

            block = Block(data['index'], block_transactions,
                          data['previous_hash'], data['miner_address'])
            block.timestamp = data['timestamp']
            block.nonce = data['nonce']
            block.hash = data['hash']
            block.merkle_root = data['merkle_root']

            # Validate block
            if (block.hash == block.calculate_hash() and
                    block.previous_hash == self.blockchain.get_latest_block().hash and
                    block.index == len(self.blockchain.chain)):

                self.blockchain.chain.append(block)
                # Remove mined transactions from pending
                for tx in block_transactions:
                    if tx in self.blockchain.pending_transactions:
                        self.blockchain.pending_transactions.remove(tx)

                return jsonify({'message': 'Block received and added'})

            return jsonify({'message': 'Invalid block'}), 400

        @self.app.route('/status', methods=['GET'])
        def get_status():
            return jsonify({
                'node_id': self.blockchain.node_id,
                'chain_length': len(self.blockchain.chain),
                'pending_transactions': len(self.blockchain.pending_transactions),
                'connected_nodes': list(self.blockchain.nodes),
                'auto_mining': self.auto_mining
            })

        @self.app.route('/auto_mine', methods=['POST'])
        def toggle_auto_mining():
            data = request.get_json()
            self.auto_mining = data.get('enabled', False)
            miner_address = data.get('miner_address', f'miner_{self.port}')

            if self.auto_mining:
                self.start_auto_mining(miner_address)
                return jsonify({'message': 'Auto mining started'})
            else:
                self.stop_auto_mining()
                return jsonify({'message': 'Auto mining stopped'})

    def broadcast_transaction(self, transaction):
        for node in self.blockchain.nodes:
            try:
                requests.post(f'http://{node}/broadcast/transaction',
                              json=transaction.to_dict(), timeout=5)
            except requests.exceptions.RequestException:
                pass

    def broadcast_block(self, block):
        for node in self.blockchain.nodes:
            try:
                requests.post(f'http://{node}/broadcast/block',
                              json=block.to_dict(), timeout=5)
            except requests.exceptions.RequestException:
                pass

    def resolve_conflicts(self):
        neighbours = self.blockchain.nodes
        new_chain = None
        max_length = len(self.blockchain.chain)

        for node in neighbours:
            try:
                response = requests.get(f'http://{node}/chain', timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    length = len(data['chain'])
                    chain = data['chain']

                    if length > max_length and self.blockchain.validate_imported_chain(chain):
                        max_length = length
                        new_chain = chain
            except requests.exceptions.RequestException:
                continue

        if new_chain:
            self.blockchain.chain = self.blockchain.dict_chain_to_objects(new_chain)
            return True

        return False

    def start_auto_sync(self, interval=30):
        def sync_periodically():
            while True:
                time.sleep(interval)
                try:
                    self.resolve_conflicts()
                except Exception as e:
                    print(f"Sync error: {e}")

        sync_thread = threading.Thread(target=sync_periodically, daemon=True)
        sync_thread.start()

    def start_auto_mining(self, miner_address):
        def mine_continuously():
            while self.auto_mining:
                if self.blockchain.pending_transactions:
                    block = self.blockchain.mine_pending_transactions(miner_address)
                    self.broadcast_block(block)
                time.sleep(10)  # Wait 10 seconds between mining attempts

        if not self.mining_thread or not self.mining_thread.is_alive():
            self.mining_thread = threading.Thread(target=mine_continuously, daemon=True)
            self.mining_thread.start()

    def stop_auto_mining(self):
        self.auto_mining = False
        if self.mining_thread:
            self.mining_thread = None

    def run(self, debug=False):
        # Start auto-sync
        self.start_auto_sync()
        print(f"Blockchain node running on {self.host}:{self.port}")
        print(f"Node ID: {self.blockchain.node_id}")
        self.app.run(host=self.host, port=self.port, debug=debug, threaded=True)


# Contoh penggunaan
if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    node = BlockchainNode(port=port)
    node.run(debug=True)