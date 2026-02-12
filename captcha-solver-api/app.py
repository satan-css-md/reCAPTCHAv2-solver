from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, User, APIToken, Transaction, Deposit, CAPTCHASolve, BitcoinAddress
from bitcoin_manager import MockBitcoinWalletManager
from config import config
import os
import secrets
import string
from datetime import datetime, timedelta
from functools import wraps
import json

# Initialize Flask app
app = Flask(__name__)
config_name = os.getenv('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# Initialize extensions
db.init_app(app)
jwt = JWTManager(app)
CORS(app)
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=[app.config['API_RATE_LIMIT']])

# Initialize Bitcoin wallet manager
bitcoin_manager = MockBitcoinWalletManager(network=app.config['BITCOIN_NETWORK'])

# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per hour")
def register():
    """Register a new user"""
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password') or not data.get('email'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    # Create new user
    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    
    # Generate Bitcoin address
    wallet_info = bitcoin_manager.generate_address_for_user(user.id)
    
    btc_addr = BitcoinAddress(
        user_id=user.id,
        address=wallet_info['address'],
        public_key=wallet_info['public_key']
    )
    user.wallet_address = wallet_info['address']
    
    db.session.add(user)
    db.session.add(btc_addr)
    db.session.commit()
    
    # Generate initial API token
    token_string = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    api_token = APIToken(user_id=user.id, token=token_string, name='Default Token')
    db.session.add(api_token)
    db.session.commit()
    
    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict(),
        'initial_api_token': token_string,
        'wallet_address': wallet_info['address']
    }), 201

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per hour")
def login():
    """Login user"""
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'User account is inactive'}), 403
    
    access_token = create_access_token(identity=user.id)
    
    return jsonify({
        'access_token': access_token,
        'user': user.to_dict()
    }), 200

# ============================================================================
# User Profile Routes
# ============================================================================

@app.route('/api/user/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200

@app.route('/api/user/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    if 'email' in data:
        if User.query.filter_by(email=data['email']).first() and user.email != data['email']:
            return jsonify({'error': 'Email already exists'}), 409
        user.email = data['email']
    
    if 'password' in data:
        user.set_password(data['password'])
    
    user.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'message': 'Profile updated',
        'user': user.to_dict()
    }), 200

# ============================================================================
# API Token Routes
# ============================================================================

@app.route('/api/api-tokens', methods=['GET'])
@jwt_required()
def get_api_tokens():
    """Get user's API tokens"""
    user_id = get_jwt_identity()
    tokens = APIToken.query.filter_by(user_id=user_id).all()
    
    return jsonify({
        'tokens': [t.to_dict() for t in tokens]
    }), 200

@app.route('/api/api-tokens', methods=['POST'])
@jwt_required()
def create_api_token():
    """Create a new API token"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    token_string = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    api_token = APIToken(
        user_id=user_id,
        token=token_string,
        name=data.get('name', f'Token {datetime.utcnow().strftime("%Y-%m-%d %H:%M")}')
    )
    db.session.add(api_token)
    db.session.commit()
    
    return jsonify({
        'message': 'API token created',
        'token': token_string,  # Only shown once during creation
        'token_id': api_token.id
    }), 201

@app.route('/api/api-tokens/<token_id>', methods=['DELETE'])
@jwt_required()
def delete_api_token(token_id):
    """Delete an API token"""
    user_id = get_jwt_identity()
    token = APIToken.query.filter_by(id=token_id, user_id=user_id).first()
    
    if not token:
        return jsonify({'error': 'Token not found'}), 404
    
    db.session.delete(token)
    db.session.commit()
    
    return jsonify({'message': 'API token deleted'}), 200

# ============================================================================
# Bitcoin Deposit Routes
# ============================================================================

@app.route('/api/wallet/address', methods=['GET'])
@jwt_required()
def get_wallet_address():
    """Get user's Bitcoin wallet address"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    btc_addr = BitcoinAddress.query.filter_by(user_id=user_id).first()
    
    if not btc_addr:
        return jsonify({'error': 'Wallet not found'}), 404
    
    # Get current balance
    balance_info = bitcoin_manager.get_address_balance(btc_addr.address)
    
    return jsonify({
        'address': btc_addr.address,
        'balance': balance_info,
        'qr_code_url': f'/api/wallet/qr/{btc_addr.address}',
        'network': app.config['BITCOIN_NETWORK']
    }), 200

@app.route('/api/wallet/transactions', methods=['GET'])
@jwt_required()
def get_wallet_transactions():
    """Get deposit transactions for user's wallet"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get transactions from database
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.received_at.desc()).all()
    
    return jsonify({
        'transactions': [t.to_dict() for t in transactions],
        'total_received': sum(t.amount_usd for t in transactions if t.status in ['confirmed', 'credited'])
    }), 200

@app.route('/api/wallet/deposits', methods=['GET'])
@jwt_required()
def get_deposit_aggregations():
    """Get aggregated deposits"""
    user_id = get_jwt_identity()
    
    deposits = Deposit.query.filter_by(user_id=user_id).order_by(Deposit.created_at.desc()).all()
    
    return jsonify({
        'deposits': [d.to_dict() for d in deposits]
    }), 200

@app.route('/api/wallet/check-deposits', methods=['POST'])
@jwt_required()
def check_for_deposits():
    """Check wallet for new deposits (admin/system endpoint)"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    btc_addr = BitcoinAddress.query.filter_by(user_id=user_id).first()
    
    if not btc_addr:
        return jsonify({'error': 'Wallet not found'}), 404
    
    # Get transactions from blockchain
    blockchain_txs = bitcoin_manager.get_address_transactions(btc_addr.address)
    
    processed_txs = []
    btc_price = bitcoin_manager.get_btc_price()
    
    for tx in blockchain_txs:
        # Check if transaction exists in database
        existing_tx = Transaction.query.filter_by(txid=tx['txid']).first()
        
        if not existing_tx and tx['amount_btc'] > 0:
            # Create new transaction
            amount_usd = tx['amount_btc'] * btc_price
            new_tx = Transaction(
                user_id=user_id,
                txid=tx['txid'],
                amount_btc=tx['amount_btc'],
                amount_usd=amount_usd,
                confirmations=tx['confirmations'],
                status='pending'
            )
            db.session.add(new_tx)
            processed_txs.append(new_tx.to_dict())
        
        elif existing_tx:
            # Update confirmation count
            if existing_tx.confirmations < app.config['CONFIRMATION_THRESHOLD'] and tx['confirmations'] >= app.config['CONFIRMATION_THRESHOLD']:
                existing_tx.confirmations = tx['confirmations']
                existing_tx.status = 'confirmed'
                existing_tx.confirmed_at = datetime.utcnow()
                
                # Update or create deposit aggregation
                update_deposit_balance(user_id, existing_tx)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Deposit check completed',
        'new_transactions': len(processed_txs),
        'processed': processed_txs
    }), 200

def update_deposit_balance(user_id, transaction):
    """Update deposit balance and credit if >= $15"""
    user = User.query.get(user_id)
    
    if not user:
        return
    
    # Get or create current pending deposit
    deposit = Deposit.query.filter_by(user_id=user_id, status='pending').first()
    
    if not deposit:
        deposit = Deposit(user_id=user_id, status='pending')
        db.session.add(deposit)
    
    deposit.total_btc += transaction.amount_btc
    deposit.total_usd += transaction.amount_usd
    deposit.updated_at = datetime.utcnow()
    
    # Add to transaction list
    existing_ids = set(deposit.transaction_ids.split(',')) if deposit.transaction_ids else set()
    existing_ids.add(transaction.id)
    deposit.transaction_ids = ','.join(existing_ids)
    
    # Check if reached minimum deposit
    if deposit.total_usd >= app.config['MIN_DEPOSIT']:
        # Credit the deposit
        deposit.status = 'credited'
        deposit.credited_amount = deposit.total_usd
        user.balance += deposit.total_usd
        transaction.status = 'credited'
        transaction.credited_at = datetime.utcnow()
    
    elif deposit.total_usd < app.config['MIN_DEPOSIT'] and deposit.total_usd > 0:
        deposit.status = 'partial'

# ============================================================================
# CAPTCHA Solving API Routes
# ============================================================================

def verify_api_token(f):
    """Decorator to verify API token from request"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_token = request.headers.get('X-API-Token') or request.headers.get('Authorization')
        
        if not api_token:
            return jsonify({'error': 'Missing API token'}), 401
        
        # Remove 'Bearer ' prefix if present
        if api_token.startswith('Bearer '):
            api_token = api_token[7:]
        
        token_obj = APIToken.query.filter_by(token=api_token).first()
        
        if not token_obj or not token_obj.is_active:
            return jsonify({'error': 'Invalid API token'}), 401
        
        user = User.query.get(token_obj.user_id)
        
        if not user or not user.is_active:
            return jsonify({'error': 'User account inactive'}), 403
        
        # Check balance
        if user.balance < app.config['CAPTCHA_PRICE']:
            return jsonify({'error': 'Insufficient balance. Minimum required: $0.001'}), 402
        
        # Update last used
        token_obj.last_used = datetime.utcnow()
        db.session.commit()
        
        # Pass user and token to route
        return f(user, token_obj, *args, **kwargs)
    
    return decorated_function

@app.route('/api/captcha/solve', methods=['POST'])
@limiter.limit("100 per hour")
@verify_api_token
def solve_captcha(user, token):
    """Solve a CAPTCHA"""
    data = request.get_json()
    
    if not data or (not data.get('website_url') and not data.get('recaptcha_key')):
        return jsonify({'error': 'Missing website_url or recaptcha_key'}), 400
    
    # Create CAPTCHA solve record
    captcha_solve = CAPTCHASolve(
        user_id=user.id,
        api_key=token.id,
        website_url=data.get('website_url'),
        recaptcha_key=data.get('recaptcha_key'),
        status='pending',
        cost=app.config['CAPTCHA_PRICE']
    )
    
    db.session.add(captcha_solve)
    db.session.commit()
    
    # TODO: Integrate with actual reCAPTCHA solver
    # For now, simulate solving
    import time
    start_time = time.time()
    
    # Simulate solving
    captcha_solve.status = 'success'
    captcha_solve.solution = f"g_response_mock_{captcha_solve.id}"
    captcha_solve.completed_at = datetime.utcnow()
    captcha_solve.inference_time_ms = (time.time() - start_time) * 1000
    
    # Deduct cost from user balance
    user.balance -= app.config['CAPTCHA_PRICE']
    
    db.session.commit()
    
    return jsonify({
        'message': 'CAPTCHA solved successfully',
        'captcha_solve': captcha_solve.to_dict(),
        'solution': captcha_solve.solution,
        'remaining_balance': round(user.balance, 4)
    }), 200

@app.route('/api/captcha/status/<captcha_id>', methods=['GET'])
@jwt_required()
def get_captcha_status(captcha_id):
    """Get CAPTCHA solve status"""
    user_id = get_jwt_identity()
    
    captcha_solve = CAPTCHASolve.query.filter_by(id=captcha_id, user_id=user_id).first()
    
    if not captcha_solve:
        return jsonify({'error': 'CAPTCHA solve not found'}), 404
    
    return jsonify(captcha_solve.to_dict()), 200

@app.route('/api/captcha/history', methods=['GET'])
@jwt_required()
def get_captcha_history():
    """Get user's CAPTCHA solving history"""
    user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    
    query = CAPTCHASolve.query.filter_by(user_id=user_id).order_by(CAPTCHASolve.created_at.desc())
    total = query.count()
    
    captcha_solves = query.limit(limit).offset((page - 1) * limit).all()
    
    return jsonify({
        'captcha_solves': [c.to_dict() for c in captcha_solves],
        'total': total,
        'page': page,
        'limit': limit,
        'total_pages': (total + limit - 1) // limit
    }), 200

# ============================================================================
# Dashboard & Stats Routes
# ============================================================================

@app.route('/api/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    """Get user dashboard"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Calculate stats
    total_solves = CAPTCHASolve.query.filter_by(user_id=user_id).count()
    successful_solves = CAPTCHASolve.query.filter_by(user_id=user_id, status='success').count()
    total_spent = CAPTCHASolve.query.filter_by(user_id=user_id, status='success').with_entities(db.func.sum(CAPTCHASolve.cost)).scalar() or 0
    
    avg_time = db.session.query(db.func.avg(CAPTCHASolve.inference_time_ms)).filter_by(user_id=user_id, status='success').scalar()
    
    return jsonify({
        'user': user.to_dict(),
        'stats': {
            'total_solves': total_solves,
            'successful_solves': successful_solves,
            'success_rate': (successful_solves / total_solves * 100) if total_solves > 0 else 0,
            'total_spent': round(total_spent, 4),
            'average_solve_time_ms': round(avg_time, 2) if avg_time else 0
        },
        'wallet': {
            'address': user.wallet_address,
            'balance': round(user.balance, 4)
        }
    }), 200

# ============================================================================
# Documentation Routes
# ============================================================================

@app.route('/api/docs', methods=['GET'])
def get_api_docs():
    """Get API documentation"""
    docs = {
        'title': 'CAPTCHA Solver API',
        'version': '1.0.0',
        'description': 'API for solving Google reCAPTCHAv2 challenges',
        'base_url': request.base_url.rstrip('/'),
        'endpoints': {
            'auth': {
                'register': {
                    'method': 'POST',
                    'path': '/api/auth/register',
                    'description': 'Register a new user account',
                    'body': {
                        'username': 'string',
                        'email': 'string',
                        'password': 'string'
                    },
                    'response': {
                        'user': 'User object',
                        'initial_api_token': 'string',
                        'wallet_address': 'string'
                    }
                },
                'login': {
                    'method': 'POST',
                    'path': '/api/auth/login',
                    'description': 'Login to existing account',
                    'body': {
                        'username': 'string',
                        'password': 'string'
                    },
                    'response': {
                        'access_token': 'JWT token',
                        'user': 'User object'
                    }
                }
            },
            'captcha': {
                'solve': {
                    'method': 'POST',
                    'path': '/api/captcha/solve',
                    'description': 'Solve a reCAPTCHA challenge',
                    'headers': {
                        'X-API-Token': 'Your API token'
                    },
                    'body': {
                        'website_url': 'string (optional)',
                        'recaptcha_key': 'string (optional)'
                    },
                    'cost': '$0.001 per challenge',
                    'response': {
                        'solution': 'g-response token',
                        'remaining_balance': 'float'
                    }
                },
                'history': {
                    'method': 'GET',
                    'path': '/api/captcha/history',
                    'description': 'Get CAPTCHA solving history',
                    'headers': {
                        'Authorization': 'Bearer {access_token}'
                    },
                    'query_params': {
                        'page': 'integer (default: 1)',
                        'limit': 'integer (default: 50)'
                    }
                }
            },
            'wallet': {
                'get_address': {
                    'method': 'GET',
                    'path': '/api/wallet/address',
                    'description': 'Get your Bitcoin wallet address for deposits',
                    'headers': {
                        'Authorization': 'Bearer {access_token}'
                    }
                },
                'transactions': {
                    'method': 'GET',
                    'path': '/api/wallet/transactions',
                    'description': 'Get transaction history',
                    'headers': {
                        'Authorization': 'Bearer {access_token}'
                    }
                },
                'check_deposits': {
                    'method': 'POST',
                    'path': '/api/wallet/check-deposits',
                    'description': 'Check for new Bitcoin deposits',
                    'headers': {
                        'Authorization': 'Bearer {access_token}'
                    }
                }
            },
            'api_tokens': {
                'list': {
                    'method': 'GET',
                    'path': '/api/api-tokens',
                    'description': 'List all API tokens for user'
                },
                'create': {
                    'method': 'POST',
                    'path': '/api/api-tokens',
                    'description': 'Create new API token',
                    'body': {
                        'name': 'string (optional)'
                    }
                },
                'delete': {
                    'method': 'DELETE',
                    'path': '/api/api-tokens/<token_id>',
                    'description': 'Delete API token'
                }
            }
        },
        'pricing': {
            'per_captcha': '$0.001',
            'minimum_deposit': '$15.00',
            'supported_currencies': ['BTC']
        },
        'deposit_info': {
            'network': app.config['BITCOIN_NETWORK'],
            'confirmation_required': app.config['CONFIRMATION_THRESHOLD'],
            'min_deposit_usd': app.config['MIN_DEPOSIT']
        }
    }
    
    return jsonify(docs), 200

# ============================================================================
# Health Check
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'bitcoin_network': app.config['BITCOIN_NETWORK'],
        'btc_price_usd': bitcoin_manager.get_btc_price()
    }), 200

# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(429)
def rate_limit_exceeded(error):
    """Handle rate limit exceeded"""
    return jsonify({'error': 'Rate limit exceeded'}), 429

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================================
# Database initialization
# ============================================================================

@app.cli.command()
def init_db():
    """Initialize the database"""
    db.create_all()
    print('Database initialized')

@app.cli.command()
def drop_db():
    """Drop all database tables"""
    db.drop_all()
    print('Database dropped')

# ============================================================================
# App entrypoint
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
