from urllib.parse import urlparse
import json
import os
import re
from datetime import datetime

from block import Block
from portfolio import Portfolio
from transaction import Transaction


class Blockchain:
    def __init__(self, node_id):
        self.node_id = node_id
        self.difficulty = 4
        self.pending_transactions = []
        self.mining_reward = 50
        self.nodes = set()
        self.blocks_file = f"blocks_{node_id}.txt"
        self.chain_json_file = f"chain_{node_id}.json"

        # Try to load existing blockchain, otherwise create genesis
        if not self.load_blockchain_from_file():
            self.chain = [self.create_genesis_block()]
            self.save_blockchain_state()

        self.portfolio = Portfolio(self)

    def create_genesis_block(self):
        genesis_transactions = []
        genesis_block = Block(0, genesis_transactions, "0", "genesis")
        genesis_block.hash = genesis_block.calculate_hash()
        return genesis_block

    def get_latest_block(self):
        return self.chain[-1]

    def load_blockchain_from_file(self):
        """Load the entire blockchain from JSON file on startup"""
        try:
            if os.path.exists(self.chain_json_file):
                print(f"Loading blockchain from {self.chain_json_file}...")
                with open(self.chain_json_file, 'r') as f:
                    chain_data = json.load(f)

                # Convert dictionary chain back to Block objects
                self.chain = self.dict_chain_to_objects(chain_data['chain'])
                self.difficulty = chain_data.get('difficulty', 4)
                self.mining_reward = chain_data.get('mining_reward', 50)

                # Load pending transactions if any
                pending_tx_data = chain_data.get('pending_transactions', [])
                self.pending_transactions = []
                for tx_dict in pending_tx_data:
                    tx = Transaction(tx_dict['sender'], tx_dict['recipient'],
                                     tx_dict['amount'], tx_dict['fee'])
                    tx.id = tx_dict['id']
                    tx.timestamp = tx_dict['timestamp']
                    tx.signature = tx_dict['signature']
                    self.pending_transactions.append(tx)

                print(f"Successfully loaded blockchain with {len(self.chain)} blocks")
                return True

        except Exception as e:
            print(f"Error loading blockchain from file: {e}")
            print("Starting with fresh blockchain...")

        return False

    def read_last_block_from_text_file(self):
        """Alternative method to read just the last block from text file"""
        try:
            if not os.path.exists(self.blocks_file):
                return None

            with open(self.blocks_file, 'r') as f:
                content = f.read()

            # Find all block sections
            block_pattern = r'BLOCK #(\d+)\n.*?(?=BLOCK #|\Z)'
            blocks = re.findall(block_pattern, content, re.DOTALL)

            if not blocks:
                return None

            # Get the last block section
            last_block_match = re.search(r'BLOCK #(\d+)\n(.*?)(?=BLOCK #|\Z)', content, re.DOTALL)
            if not last_block_match:
                return None

            block_index = int(last_block_match.group(1))
            block_content = last_block_match.group(2)

            # Parse block details
            timestamp_match = re.search(r'Timestamp: (.*?)\n', block_content)
            prev_hash_match = re.search(r'Previous Hash: (.*?)\n', block_content)
            hash_match = re.search(r'Hash: (.*?)\n', block_content)
            merkle_match = re.search(r'Merkle Root: (.*?)\n', block_content)
            nonce_match = re.search(r'Nonce: (.*?)\n', block_content)
            miner_match = re.search(r'Miner: (.*?)\n', block_content)

            if not all([timestamp_match, prev_hash_match, hash_match, miner_match]):
                return None

            # Parse transactions
            transactions = []
            tx_pattern = r'\d+\. (.*?) -> (.*?): ([\d.]+) \(fee: ([\d.]+)\)\n\s+ID: (.*?)\n\s+Timestamp: (.*?)\n'
            tx_matches = re.findall(tx_pattern, block_content)

            for tx_match in tx_matches:
                sender, recipient, amount, fee, tx_id, tx_timestamp = tx_match
                tx = Transaction(sender, recipient, float(amount), float(fee))
                tx.id = tx_id
                # Parse timestamp string back to timestamp
                tx_dt = datetime.strptime(tx_timestamp, '%Y-%m-%d %H:%M:%S.%f')
                tx.timestamp = tx_dt.timestamp()
                transactions.append(tx)

            # Create block object
            block = Block(block_index, transactions, prev_hash_match.group(1), miner_match.group(1))

            # Parse and set timestamp
            block_dt = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S.%f')
            block.timestamp = block_dt.timestamp()

            block.hash = hash_match.group(1)
            block.merkle_root = merkle_match.group(1) if merkle_match else ""
            block.nonce = int(nonce_match.group(1)) if nonce_match else 0

            return block

        except Exception as e:
            print(f"Error reading last block from text file: {e}")
            return None

    def save_blockchain_state(self):
        """Save the entire blockchain state to JSON file"""
        try:
            blockchain_data = {
                'chain': [block.to_dict() for block in self.chain],
                'pending_transactions': [tx.to_dict() for tx in self.pending_transactions],
                'difficulty': self.difficulty,
                'mining_reward': self.mining_reward,
                'node_id': self.node_id,
                'last_updated': datetime.now().isoformat()
            }

            with open(self.chain_json_file, 'w') as f:
                json.dump(blockchain_data, f, indent=2)

            print(f"Blockchain state saved to {self.chain_json_file}")
            return True

        except Exception as e:
            print(f"Error saving blockchain state: {e}")
            return False

    def add_transaction(self, transaction):
        if self.validate_transaction(transaction):
            transaction.sign_transaction()
            self.pending_transactions.append(transaction)
            # Save state after adding transaction
            self.save_blockchain_state()
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

    def save_block_to_file(self, block):
        """Save a new block to the text file"""
        try:
            # Create the file if it doesn't exist
            if not os.path.exists(self.blocks_file):
                with open(self.blocks_file, 'w') as f:
                    f.write(f"Blockchain Blocks for Node: {self.node_id}\n")
                    f.write("=" * 50 + "\n\n")

            # Append the new block to the file
            with open(self.blocks_file, 'a') as f:
                f.write(f"BLOCK #{block.index}\n")
                f.write(f"Timestamp: {datetime.fromtimestamp(block.timestamp)}\n")
                f.write(f"Previous Hash: {block.previous_hash}\n")
                f.write(f"Hash: {block.hash}\n")
                f.write(f"Merkle Root: {block.merkle_root}\n")
                f.write(f"Nonce: {block.nonce}\n")
                f.write(f"Miner: {block.miner_address}\n")
                f.write(f"Transactions ({len(block.transactions)}):\n")

                for i, tx in enumerate(block.transactions, 1):
                    f.write(f"  {i}. {tx.sender} -> {tx.recipient}: {tx.amount} (fee: {tx.fee})\n")
                    f.write(f"     ID: {tx.id}\n")
                    f.write(f"     Timestamp: {datetime.fromtimestamp(tx.timestamp)}\n")

                f.write("-" * 50 + "\n\n")

            print(f"Block #{block.index} saved to {self.blocks_file}")
            return True

        except Exception as e:
            print(f"Error saving block to file: {e}")
            return False

    def save_block_to_json_file(self, block):
        """Alternative method to save block as JSON"""
        json_file = f"block_{block.index}_{self.node_id}.json"
        try:
            with open(json_file, 'w') as f:
                json.dump(block.to_dict(), f, indent=2)
            print(f"Block #{block.index} saved as JSON to {json_file}")
            return True
        except Exception as e:
            print(f"Error saving block as JSON: {e}")
            return False

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

        # Save the new block to text file
        self.save_block_to_file(block)

        # Save the complete blockchain state
        self.save_blockchain_state()

        print(f"Block successfully mined by {mining_reward_address}")
        return block

    def save_entire_chain_to_file(self):
        """Save the entire blockchain to a file"""
        chain_file = f"full_chain_{self.node_id}.txt"
        try:
            with open(chain_file, 'w') as f:
                f.write(f"Complete Blockchain for Node: {self.node_id}\n")
                f.write(f"Generated on: {datetime.now()}\n")
                f.write("=" * 60 + "\n\n")

                for block in self.chain:
                    f.write(f"BLOCK #{block.index}\n")
                    f.write(f"Timestamp: {datetime.fromtimestamp(block.timestamp)}\n")
                    f.write(f"Previous Hash: {block.previous_hash}\n")
                    f.write(f"Hash: {block.hash}\n")
                    f.write(f"Merkle Root: {block.merkle_root}\n")
                    f.write(f"Nonce: {block.nonce}\n")
                    f.write(f"Miner: {block.miner_address}\n")
                    f.write(f"Transactions ({len(block.transactions)}):\n")

                    for i, tx in enumerate(block.transactions, 1):
                        f.write(f"  {i}. {tx.sender} -> {tx.recipient}: {tx.amount} (fee: {tx.fee})\n")
                        f.write(f"     ID: {tx.id}\n")
                        f.write(f"     Timestamp: {datetime.fromtimestamp(tx.timestamp)}\n")

                    f.write("-" * 60 + "\n\n")

            print(f"Complete blockchain saved to {chain_file}")
            return True

        except Exception as e:
            print(f"Error saving complete chain: {e}")
            return False

    def get_blockchain_info(self):
        """Get current blockchain information"""
        return {
            'total_blocks': len(self.chain),
            'pending_transactions': len(self.pending_transactions),
            'latest_block_hash': self.get_latest_block().hash,
            'latest_block_index': self.get_latest_block().index,
            'difficulty': self.difficulty,
            'mining_reward': self.mining_reward,
            'node_id': self.node_id
        }

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
            # Save the new chain state
            self.save_blockchain_state()
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