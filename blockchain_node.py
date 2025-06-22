import threading
import time
import os

import requests
from flask import Flask, jsonify, request, render_template

from block import Block
from blockchain import Blockchain
from transaction import Transaction


class BlockchainNode:
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.node_id = f"{host}:{port}"

        # Initialize blockchain with recovery capability
        print(f"Initializing blockchain node {self.node_id}...")
        self.blockchain = Blockchain(self.node_id)

        # Print recovery status
        chain_info = self.blockchain.get_blockchain_info()
        print(f"Blockchain loaded with {chain_info['total_blocks']} blocks")
        print(f"Pending transactions: {chain_info['pending_transactions']}")

        self.app = Flask(__name__)
        self.setup_routes()
        self.sync_timer = None
        self.mining_thread = None
        self.auto_mining = False
        self.auto_save = True  # Enable automatic state saving

    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')

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
                'block': block.to_dict(),
                'chain_length': len(self.blockchain.chain)
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
                    'transaction': transaction.to_dict(),
                    'pending_count': len(self.blockchain.pending_transactions)
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

            # Save state after registering nodes
            if self.auto_save:
                self.blockchain.save_blockchain_state()

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
                    'new_chain': [block.to_dict() for block in self.blockchain.chain],
                    'chain_length': len(self.blockchain.chain)
                }
            else:
                response = {
                    'message': 'Chain is authoritative',
                    'chain': [block.to_dict() for block in self.blockchain.chain],
                    'chain_length': len(self.blockchain.chain)
                }

            return jsonify(response)

        @self.app.route('/sync', methods=['POST'])
        def sync_chain():
            data = request.get_json()
            new_chain = data.get('chain')

            if new_chain and self.blockchain.replace_chain(new_chain):
                return jsonify({
                    'message': 'Chain synchronized successfully',
                    'new_length': len(self.blockchain.chain)
                })
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

            # Check if transaction already exists
            existing_tx = any(tx.id == transaction.id for tx in self.blockchain.pending_transactions)

            if not existing_tx and self.blockchain.add_transaction(transaction):
                return jsonify({'message': 'Transaction received and added'})
            elif existing_tx:
                return jsonify({'message': 'Transaction already exists'})
            else:
                return jsonify({'message': 'Invalid transaction'}), 400

        @self.app.route('/broadcast/block', methods=['POST'])
        def receive_block():
            data = request.get_json()

            # Check if block already exists
            if any(block.index == data['index'] for block in self.blockchain.chain):
                return jsonify({'message': 'Block already exists'})

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
                    self.blockchain.pending_transactions = [
                        pending_tx for pending_tx in self.blockchain.pending_transactions
                        if pending_tx.id != tx.id
                    ]

                # Save block to text file
                self.blockchain.save_block_to_file(block)

                # Save updated blockchain state
                if self.auto_save:
                    self.blockchain.save_blockchain_state()

                return jsonify({
                    'message': 'Block received and added',
                    'block_index': block.index,
                    'chain_length': len(self.blockchain.chain)
                })

            return jsonify({'message': 'Invalid block'}), 400

        @self.app.route('/status', methods=['GET'])
        def get_status():
            chain_info = self.blockchain.get_blockchain_info()
            return jsonify({
                'node_id': self.blockchain.node_id,
                'chain_length': chain_info['total_blocks'],
                'pending_transactions': chain_info['pending_transactions'],
                'latest_block_hash': chain_info['latest_block_hash'],
                'latest_block_index': chain_info['latest_block_index'],
                'connected_nodes': list(self.blockchain.nodes),
                'auto_mining': self.auto_mining,
                'auto_save': self.auto_save,
                'difficulty': self.blockchain.difficulty,
                'mining_reward': self.blockchain.mining_reward
            })

        @self.app.route('/auto_mine', methods=['POST'])
        def toggle_auto_mining():
            data = request.get_json()
            self.auto_mining = data.get('enabled', False)
            miner_address = data.get('miner_address', f'miner_{self.port}')

            if self.auto_mining:
                self.start_auto_mining(miner_address)
                return jsonify({'message': 'Auto mining started', 'miner': miner_address})
            else:
                self.stop_auto_mining()
                return jsonify({'message': 'Auto mining stopped'})

        @self.app.route('/backup', methods=['POST'])
        def create_backup():
            """Create a manual backup of the blockchain"""
            try:
                # Save complete chain to file
                self.blockchain.save_entire_chain_to_file()

                # Save blockchain state
                self.blockchain.save_blockchain_state()

                return jsonify({
                    'message': 'Backup created successfully',
                    'files': [
                        f"full_chain_{self.blockchain.node_id}.txt",
                        f"chain_{self.blockchain.node_id}.json",
                        f"blocks_{self.blockchain.node_id}.txt"
                    ]
                })
            except Exception as e:
                return jsonify({'message': f'Backup failed: {str(e)}'}), 500

        @self.app.route('/restore', methods=['POST'])
        def restore_from_backup():
            """Restore blockchain from backup file"""
            data = request.get_json()
            backup_file = data.get('backup_file')

            if not backup_file:
                return jsonify({'message': 'No backup file specified'}), 400

            try:
                if not os.path.exists(backup_file):
                    return jsonify({'message': 'Backup file not found'}), 404

                # Try to load from the backup
                old_chain_length = len(self.blockchain.chain)

                # This would require implementing a restore method
                # For now, just return the current status
                return jsonify({
                    'message': 'Restore functionality not yet implemented',
                    'current_chain_length': old_chain_length
                })

            except Exception as e:
                return jsonify({'message': f'Restore failed: {str(e)}'}), 500

        @self.app.route('/settings', methods=['GET', 'POST'])
        def node_settings():
            if request.method == 'GET':
                return jsonify({
                    'auto_save': self.auto_save,
                    'auto_mining': self.auto_mining,
                    'difficulty': self.blockchain.difficulty,
                    'mining_reward': self.blockchain.mining_reward
                })
            else:
                data = request.get_json()

                if 'auto_save' in data:
                    self.auto_save = data['auto_save']

                if 'difficulty' in data:
                    self.blockchain.difficulty = data['difficulty']

                if 'mining_reward' in data:
                    self.blockchain.mining_reward = data['mining_reward']

                # Save settings
                if self.auto_save:
                    self.blockchain.save_blockchain_state()

                return jsonify({'message': 'Settings updated'})

    def broadcast_transaction(self, transaction):
        """Broadcast transaction to all connected nodes"""
        for node in self.blockchain.nodes:
            try:
                response = requests.post(f'http://{node}/broadcast/transaction',
                                         json=transaction.to_dict(), timeout=5)
                if response.status_code == 200:
                    print(f"Transaction broadcasted to {node}")
            except requests.exceptions.RequestException as e:
                print(f"Failed to broadcast transaction to {node}: {e}")

    def broadcast_block(self, block):
        """Broadcast block to all connected nodes"""
        for node in self.blockchain.nodes:
            try:
                response = requests.post(f'http://{node}/broadcast/block',
                                         json=block.to_dict(), timeout=5)
                if response.status_code == 200:
                    print(f"Block broadcasted to {node}")
            except requests.exceptions.RequestException as e:
                print(f"Failed to broadcast block to {node}: {e}")

    def resolve_conflicts(self):
        """Resolve conflicts with other nodes using consensus"""
        neighbours = self.blockchain.nodes
        new_chain = None
        max_length = len(self.blockchain.chain)

        print(f"Resolving conflicts with {len(neighbours)} neighbors...")

        for node in neighbours:
            try:
                response = requests.get(f'http://{node}/chain', timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    length = len(data['chain'])
                    chain = data['chain']

                    print(f"Node {node} has chain length: {length}")

                    if length > max_length and self.blockchain.validate_imported_chain(chain):
                        max_length = length
                        new_chain = chain
                        print(f"Found longer valid chain from {node}")
            except requests.exceptions.RequestException as e:
                print(f"Failed to connect to {node}: {e}")
                continue

        if new_chain:
            old_length = len(self.blockchain.chain)
            self.blockchain.chain = self.blockchain.dict_chain_to_objects(new_chain)

            # Save the new chain state
            if self.auto_save:
                self.blockchain.save_blockchain_state()

            print(f"Chain replaced: {old_length} -> {len(self.blockchain.chain)} blocks")
            return True

        print("Chain is authoritative")
        return False

    def start_auto_sync(self, interval=30):
        """Start automatic synchronization with other nodes"""

        def sync_periodically():
            while True:
                time.sleep(interval)
                try:
                    if self.blockchain.nodes:
                        print("Performing periodic sync...")
                        self.resolve_conflicts()
                except Exception as e:
                    print(f"Sync error: {e}")

        sync_thread = threading.Thread(target=sync_periodically, daemon=True)
        sync_thread.start()
        print(f"Auto-sync started (interval: {interval}s)")

    def start_auto_mining(self, miner_address):
        """Start automatic mining"""

        def mine_continuously():
            print(f"Auto-mining started for {miner_address}")
            while self.auto_mining:
                try:
                    if self.blockchain.pending_transactions:
                        print(f"Mining {len(self.blockchain.pending_transactions)} pending transactions...")
                        block = self.blockchain.mine_pending_transactions(miner_address)
                        self.broadcast_block(block)
                        print(f"Block #{block.index} mined and broadcasted")
                    else:
                        print("No pending transactions to mine")
                except Exception as e:
                    print(f"Mining error: {e}")

                time.sleep(10)  # Wait 10 seconds between mining attempts

            print("Auto-mining stopped")

        if not self.mining_thread or not self.mining_thread.is_alive():
            self.mining_thread = threading.Thread(target=mine_continuously, daemon=True)
            self.mining_thread.start()

    def stop_auto_mining(self):
        """Stop automatic mining"""
        self.auto_mining = False
        if self.mining_thread:
            self.mining_thread = None

    def graceful_shutdown(self):
        """Perform graceful shutdown with state saving"""
        print("Performing graceful shutdown...")

        # Stop auto mining
        self.stop_auto_mining()

        # Save final state
        if self.auto_save:
            self.blockchain.save_blockchain_state()
            self.blockchain.save_entire_chain_to_file()

        print("Blockchain state saved. Shutdown complete.")

    def run(self, debug=False):
        """Run the blockchain node"""
        try:
            # Start auto-sync
            self.start_auto_sync()

            print(f"Blockchain node running on {self.host}:{self.port}")
            print(f"Node ID: {self.blockchain.node_id}")
            print(f"Chain length: {len(self.blockchain.chain)} blocks")
            print(f"Pending transactions: {len(self.blockchain.pending_transactions)}")
            print(f"Auto-save: {self.auto_save}")

            self.app.run(host=self.host, port=self.port, debug=debug, threaded=True)

        except KeyboardInterrupt:
            self.graceful_shutdown()
        except Exception as e:
            print(f"Node error: {e}")
            self.graceful_shutdown()


if __name__ == '__main__':
    import sys

    # Parse command line arguments
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    host = sys.argv[2] if len(sys.argv) > 2 else '0.0.0.0'

    # Create and run node
    node = BlockchainNode(host=host, port=port)
    node.run(debug=False)