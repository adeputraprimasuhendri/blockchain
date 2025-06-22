# Blockchain Multi-Node System

A complete multi-node blockchain implementation in Python with portfolio management, transaction handling, mining capabilities, and automatic synchronization between nodes.

## Features

- 🔗 **Multi-Node Architecture**: Support for multiple blockchain nodes with automatic synchronization
- 💰 **Portfolio Management**: Track balances, transaction history, and portfolio summaries
- 🔄 **Transaction System**: Secure transaction handling with validation and digital signatures
- ⛏️ **Mining System**: Proof-of-Work mining with configurable difficulty and rewards
- 🔒 **Security**: Transaction validation, chain integrity checks, and Merkle tree implementation
- 🌐 **Auto-Sync**: Automatic synchronization between nodes with consensus mechanism
- 📊 **REST API**: Complete API for blockchain operations

## Prerequisites

- Python 3.7+
- Required packages: `flask`, `requests`

## Installation

1. **Clone or save the blockchain code** to a file named `blockchain.py`

2. **Install required dependencies:**
```bash
pip install flask requests
```

## Quick Start

### 1. Running Multiple Nodes

Open separate terminal windows for each node:

**Terminal 1 (Node 1):**
```bash
python blockchain.py 5000
```

**Terminal 2 (Node 2):**
```bash
python blockchain.py 5001
```

**Terminal 3 (Node 3):**
```bash
python blockchain.py 5002
```

### 2. Connect Nodes

Register nodes with each other to enable synchronization:

```bash
# Register Node 2 and 3 with Node 1
curl -X POST http://localhost:5000/nodes/register \
  -H "Content-Type: application/json" \
  -d '{"nodes": ["localhost:5001", "localhost:5002"]}'

# Register Node 1 and 3 with Node 2
curl -X POST http://localhost:5001/nodes/register \
  -H "Content-Type: application/json" \
  -d '{"nodes": ["localhost:5000", "localhost:5002"]}'

# Register Node 1 and 2 with Node 3
curl -X POST http://localhost:5002/nodes/register \
  -H "Content-Type: application/json" \
  -d '{"nodes": ["localhost:5000", "localhost:5001"]}'
```

### 3. Basic Operations

**Create a transaction:**
```bash
curl -X POST http://localhost:5000/transactions/new \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "alice",
    "recipient": "bob",
    "amount": 10,
    "fee": 1
  }'
```

**Mine a block:**
```bash
curl -X POST http://localhost:5000/mine \
  -H "Content-Type: application/json" \
  -d '{"miner_address": "miner1"}'
```

**Check portfolio:**
```bash
curl http://localhost:5000/portfolio/alice
```

## API Reference

### Transaction Management

#### Create New Transaction
```bash
POST /transactions/new
Content-Type: application/json

{
  "sender": "address1",
  "recipient": "address2", 
  "amount": 50,
  "fee": 2
}
```

#### Get Portfolio Summary
```bash
GET /portfolio/<address>
```

#### Get Balance
```bash
GET /balance/<address>
```

### Mining Operations

#### Mine Block
```bash
POST /mine
Content-Type: application/json

{
  "miner_address": "miner_address"
}
```

#### Enable/Disable Auto Mining
```bash
POST /auto_mine
Content-Type: application/json

{
  "enabled": true,
  "miner_address": "auto_miner"
}
```

### Blockchain Operations

#### Get Full Chain
```bash
GET /chain
```

#### Get Node Status
```bash
GET /status
```

### Network Operations

#### Register Nodes
```bash
POST /nodes/register
Content-Type: application/json

{
  "nodes": ["localhost:5001", "localhost:5002"]
}
```

#### Resolve Conflicts (Consensus)
```bash
GET /nodes/resolve
```

#### Manual Sync
```bash
POST /sync
Content-Type: application/json

{
  "chain": [blockchain_data]
}
```

## Usage Examples

### Example 1: Complete Transaction Flow

```bash
# 1. Create initial transactions
curl -X POST http://localhost:5000/transactions/new \
  -H "Content-Type: application/json" \
  -d '{"sender": "genesis", "recipient": "alice", "amount": 100}'

curl -X POST http://localhost:5000/transactions/new \
  -H "Content-Type: application/json" \
  -d '{"sender": "genesis", "recipient": "bob", "amount": 50}'

# 2. Mine the transactions
curl -X POST http://localhost:5000/mine \
  -H "Content-Type: application/json" \
  -d '{"miner_address": "miner1"}'

# 3. Check balances
curl http://localhost:5000/balance/alice
curl http://localhost:5000/balance/bob
curl http://localhost:5000/balance/miner1

# 4. Transfer between users
curl -X POST http://localhost:5000/transactions/new \
  -H "Content-Type: application/json" \
  -d '{"sender": "alice", "recipient": "bob", "amount": 25, "fee": 1}'

# 5. Mine the new transaction
curl -X POST http://localhost:5001/mine \
  -H "Content-Type: application/json" \
  -d '{"miner_address": "miner2"}'
```

### Example 2: Multi-Node Synchronization

```bash
# 1. Create transaction on Node 1
curl -X POST http://localhost:5000/transactions/new \
  -H "Content-Type: application/json" \
  -d '{"sender": "alice", "recipient": "charlie", "amount": 15}'

# 2. Mine on Node 2 (will sync automatically)
curl -X POST http://localhost:5001/mine \
  -H "Content-Type: application/json" \
  -d '{"miner_address": "miner_node2"}'

# 3. Check chain length on all nodes (should be same)
curl http://localhost:5000/status
curl http://localhost:5001/status
curl http://localhost:5002/status
```

### Example 3: Portfolio Analysis

```bash
# Get detailed portfolio for an address
curl http://localhost:5000/portfolio/alice

# Response includes:
# - Current balance
# - Transaction history
# - Number of sent/received transactions
# - Block information for each transaction
```

## Advanced Features

### Auto-Mining Mode

Enable automatic mining on a node:

```bash
curl -X POST http://localhost:5000/auto_mine \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "miner_address": "auto_miner_1"}'
```

### Monitoring Network Health

Check network status:

```bash
# Get detailed status
curl http://localhost:5000/status

# Force consensus check
curl http://localhost:5000/nodes/resolve

# View full blockchain
curl http://localhost:5000/chain
```

## Configuration

### Mining Difficulty
The mining difficulty is set to 4 by default (4 leading zeros). You can modify this in the `Blockchain` class:

```python
self.difficulty = 4  # Increase for harder mining
```

### Mining Reward
Default mining reward is 10 tokens. Modify in the `Blockchain` class:

```python
self.mining_reward = 10  # Change reward amount
```

### Sync Interval
Auto-sync occurs every 30 seconds by default. Modify in the `start_auto_sync` method:

```python
def start_auto_sync(self, interval=30):  # Change interval
```

## Architecture Overview

### Core Components

1. **Transaction Class**: Handles individual transactions with validation and signing
2. **Block Class**: Manages block creation, mining, and validation
3. **Portfolio Class**: Tracks balances and transaction history
4. **Blockchain Class**: Core blockchain logic and chain management
5. **BlockchainNode Class**: Network layer and API endpoints

### Security Features

- **Transaction Validation**: Checks sender balance and transaction validity
- **Digital Signatures**: Each transaction is signed for authenticity
- **Merkle Trees**: Ensures block integrity
- **Proof of Work**: Prevents spam and secures the network
- **Chain Validation**: Prevents tampering with blockchain history

### Network Architecture

- **Peer-to-Peer**: Nodes communicate directly with each other
- **Automatic Broadcast**: New transactions and blocks are automatically shared
- **Consensus Mechanism**: Longest valid chain wins
- **Fault Tolerance**: Network continues operating even if some nodes fail

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Use different port
   python blockchain.py 5003
   ```

2. **Node Connection Failed**
   ```bash
   # Check if target node is running
   curl http://localhost:5001/status
   ```

3. **Transaction Rejected**
   - Check sender balance
   - Verify transaction format
   - Ensure positive amount

4. **Mining Takes Too Long**
   - Reduce difficulty in blockchain.py
   - Check system resources

### Debug Mode

Run with debug information:
```bash
python blockchain.py 5000
# Debug mode is enabled by default
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Make your changes
4. Test with multiple nodes
5. Submit a pull request

## License

This project is open source and available under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation
3. Test with minimal examples
4. Check node connectivity

---

**Happy Blockchain Development! 🚀**
