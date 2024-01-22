import hashlib
import json
from time import time
from uuid import uuid4
from flask import Flask, jsonify, request, render_template
from datetime import datetime

class Blockchain(object):
    def __init__(self, name="MyChain"):
        """
        Initialize the blockchain with a name, an empty chain, and other necessary attributes.
        """
        self.name = name
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.new_block(previous_hash='1', proof=100)

    def register_node(self, address):
        """
        Add a new node to the list of nodes.
        """
        self.nodes.add(address)

    def valid_chain(self, chain):
        """
        Check if a given blockchain is valid.
        """
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        Consensus algorithm to resolve conflicts by replacing the chain with the longest one in the network.
        """
        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            response = request.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, previous_hash=None):
        """
        Create a new block in the blockchain.
        """
        block = {
            'index': len(self.chain) + 1,
            'timestamp':  datetime.fromtimestamp(time()).strftime('%Y-%m-%d %H:%M:%S'),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Adds a new transaction to the list of transactions.
        """
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        """
        Creates a SHA-256 hash of a block.
        """
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        """
        Returns the last block in the chain.
        """
        return self.chain[-1]

    def proof_of_work(self, last_proof):
        """
        Simple Proof of Work Algorithm:
         - Find a number p' such that hash(pp') contains 4 leading zeroes
         - p is the previous proof, and p' is the new proof
        """
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        Validates the proof: Does hash(last_proof, proof) contain 4 leading zeroes?
        """
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

# Flask application setup and routes
app = Flask(__name__)
node_identifier = str(uuid4()).replace('-', '')
blockchain = Blockchain()

@app.route('/')
def home():
    """
    Render the home page template with options to interact with the blockchain.
    """
    return render_template('home.html')

@app.route('/mine', methods=['GET', 'POST'])
def mine():
    """
    Mines a new block and adds it to the blockchain.
    """
    if request.method == 'POST':
        last_block = blockchain.last_block
        last_proof = last_block['proof']
        proof = blockchain.proof_of_work(last_proof)

        blockchain.new_transaction(
            sender="0",
            recipient=node_identifier,
            amount=1
        )

        previous_hash = blockchain.hash(last_block)
        block = blockchain.new_block(proof, previous_hash)

        response = {
            'message': "New Block Forged",
            'index': block['index'],
            'transactions': block['transactions'],
            'proof': block['proof'],
            'previous_hash': block['previous_hash'],
        }
        return render_template('mine_result.html', block=block, message="New Block Forged")
    else:
        return render_template('mine.html')

@app.route('/transactions/new', methods=['GET', 'POST'])
def new_transaction():
    if request.method == 'POST':
        values = request.form
        required = ['sender', 'recipient', 'amount']
        if not all(k in values for k in required):
            return 'Missing values', 400

        index = blockchain.new_transaction(values['sender'], values['recipient'], int(values['amount']))
        transaction = {
            'sender': values['sender'],
            'recipient': values['recipient'],
            'amount': int(values['amount'])
        }

        return render_template('transaction_result.html', transaction=transaction, block_index=index, message="Transaction will be added to Block")
    else:
        return render_template('transaction.html')

@app.route('/chain', methods=['GET'])
def full_chain():
    """
    Displays the full blockchain.
    """
    return render_template('chain.html', chain=blockchain.chain)

@app.route('/nodes/register', methods=['GET', 'POST'])
def register_nodes():
    """
    Registers new nodes. Handles both the form display and the node registration submission.
    """
    if request.method == 'POST':
        node = request.form['node']
        if node:
            blockchain.register_node(node)
            return render_template('node_result.html', message="New node has been added", nodes=list(blockchain.nodes))
        else:
            return "Error: Please supply a valid node", 400
    else:
        return render_template('register_node.html')

@app.route('/nodes/get', methods=['GET'])
def get_nodes():
    """
    Displays all registered nodes.
    """
    return render_template('view_nodes.html', nodes=list(blockchain.nodes))

@app.route('/nodes/delete', methods=['GET', 'POST'])
def delete_node():
    """
    Deletes a node from the list of registered nodes. Handles both the form display and the node deletion submission.
    """
    if request.method == 'POST':
        node = request.form['node']
        if node and node in blockchain.nodes:
            blockchain.nodes.remove(node)
            return render_template('delete_result.html', message="Node removed", deleted_node=node,
                                   nodes=list(blockchain.nodes))
        else:
            return render_template('delete_result.html', message="Error: Node not found or invalid", deleted_node=None,
                                   nodes=list(blockchain.nodes))
    else:
        return render_template('delete_node.html')

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    """
    Resolves conflicts between nodes' chains.
    """
    replaced = blockchain.resolve_conflicts()
    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
