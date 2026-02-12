import os
import json
import requests
from bitcoinlib.keys import Key
from bitcoinlib.wallets import Wallet, wallet_delete_if_exists
from bitcoinlib.mnemonic import Mnemonic
from datetime import datetime
from config import Config

class BitcoinWalletManager:
    """Manages Bitcoin wallet operations"""
    
    def __init__(self, network='testnet'):
        self.network = network
        self.wallet_path = 'wallets'
        if not os.path.exists(self.wallet_path):
            os.makedirs(self.wallet_path)
    
    def generate_address_for_user(self, user_id):
        """Generate a new Bitcoin address for a user"""
        try:
            # Create a new private key
            key = Key(network=self.network)
            address = key.address()
            public_key = key.public_hex
            
            # Store in wallet metadata for reference
            wallet_data = {
                'user_id': user_id,
                'address': address,
                'public_key': public_key,
                'created_at': datetime.utcnow().isoformat(),
                'network': self.network
            }
            
            return {
                'address': address,
                'public_key': public_key,
                'network': self.network
            }
        except Exception as e:
            print(f"Error generating address: {str(e)}")
            return None
    
    def get_address_balance(self, address):
        """Get balance for an address from blockchain"""
        try:
            if self.network == 'testnet':
                # Use testnet API
                url = f'https://testnet.blockchain.info/q/addressbalance/{address}'
            else:
                # Use mainnet API
                url = f'https://blockchain.info/q/addressbalance/{address}'
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Balance is in satoshis
                satoshis = int(response.text)
                btc = satoshis / 100000000  # Convert satoshis to BTC
                return {
                    'satoshis': satoshis,
                    'btc': btc,
                    'usd': btc * self.get_btc_price()
                }
        except Exception as e:
            print(f"Error getting balance: {str(e)}")
        return None
    
    def get_address_transactions(self, address, limit=50):
        """Get recent transactions for an address"""
        try:
            if self.network == 'testnet':
                url = f'https://testnet.blockchain.info/address/{address}?format=json'
            else:
                url = f'https://blockchain.info/address/{address}?format=json'
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                transactions = []
                
                for tx in data.get('txs', [])[:limit]:
                    tx_info = {
                        'txid': tx['hash'],
                        'confirmations': data.get('n_tx_unconfirmed', 0),
                        'amount_btc': 0,
                        'timestamp': tx['time']
                    }
                    
                    # Calculate received amount
                    for output in tx.get('out', []):
                        if output.get('addr') == address:
                            tx_info['amount_btc'] += output['value'] / 100000000
                    
                    transactions.append(tx_info)
                
                return transactions
        except Exception as e:
            print(f"Error getting transactions: {str(e)}")
        
        return []
    
    def get_transaction_confirmations(self, txid):
        """Get confirmation count for a transaction"""
        try:
            if self.network == 'testnet':
                url = f'https://testnet.blockchain.info/tx/{txid}?format=json'
            else:
                url = f'https://blockchain.info/tx/{txid}?format=json'
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    'confirmations': data.get('block_height', -1) if data.get('block_height') else 0,
                    'block_height': data.get('block_height'),
                    'amount_btc': sum(o['value'] for o in data.get('out', [])) / 100000000,
                    'timestamp': data.get('time')
                }
        except Exception as e:
            print(f"Error getting transaction info: {str(e)}")
        
        return None
    
    @staticmethod
    def get_btc_price():
        """Get current BTC price in USD"""
        try:
            response = requests.get(Config.BITCOIN_PRICE_API, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data['bpi']['USD']['rate_float'])
        except Exception as e:
            print(f"Error getting BTC price: {str(e)}")
        
        # Return fallback price
        return 45000.0
    
    @staticmethod
    def btc_to_usd(btc_amount):
        """Convert BTC amount to USD"""
        return btc_amount * BitcoinWalletManager.get_btc_price()
    
    @staticmethod
    def usd_to_btc(usd_amount):
        """Convert USD amount to BTC"""
        price = BitcoinWalletManager.get_btc_price()
        return usd_amount / price if price > 0 else 0

class MockBitcoinWalletManager(BitcoinWalletManager):
    """Mock Bitcoin wallet manager for testing/development"""
    
    def __init__(self, network='testnet'):
        super().__init__(network)
        self.mock_balances = {}
        self.mock_transactions = {}
    
    def generate_address_for_user(self, user_id):
        """Generate a mock Bitcoin address"""
        import secrets
        # Generate a realistic-looking testnet address
        address = f"tb1{''.join(secrets.choice('0123456789abcdefghijklmnopqrstuvwxyz') for _ in range(52))}"
        
        self.mock_balances[address] = 0
        self.mock_transactions[address] = []
        
        return {
            'address': address,
            'public_key': f"0{'0' * 65}",  # Mock public key
            'network': self.network
        }
    
    def get_address_balance(self, address):
        """Get mock balance for an address"""
        satoshis = self.mock_balances.get(address, 0)
        btc = satoshis / 100000000
        
        return {
            'satoshis': satoshis,
            'btc': btc,
            'usd': btc * self.get_btc_price()
        }
    
    def add_mock_transaction(self, address, txid, amount_btc):
        """Add a mock transaction (for testing)"""
        if address not in self.mock_transactions:
            self.mock_transactions[address] = []
        
        self.mock_transactions[address].append({
            'txid': txid,
            'confirmations': 0,
            'amount_btc': amount_btc,
            'timestamp': datetime.utcnow().timestamp()
        })
        
        # Update balance
        satoshis = int(amount_btc * 100000000)
        self.mock_balances[address] = self.mock_balances.get(address, 0) + satoshis
    
    def get_address_transactions(self, address, limit=50):
        """Get mock transactions"""
        return self.mock_transactions.get(address, [])[:limit]
    
    def confirm_mock_transaction(self, address, txid, confirmations=2):
        """Confirm a mock transaction (for testing)"""
        transactions = self.mock_transactions.get(address, [])
        for tx in transactions:
            if tx['txid'] == txid:
                tx['confirmations'] = confirmations
                break
