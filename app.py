from blockchain_node import BlockchainNode

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    node = BlockchainNode(port=port)
    node.run(debug=True)