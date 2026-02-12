from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import bcrypt

db = SQLAlchemy()

class User(db.Model):
    """User model"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    wallet_address = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    api_tokens = db.relationship('APIToken', backref='user', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    captcha_solves = db.relationship('CAPTCHASolve', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        """Check password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'balance': round(self.balance, 4),
            'wallet_address': self.wallet_address,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }

class APIToken(db.Model):
    """API Token model"""
    __tablename__ = 'api_tokens'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'token': self.token[:8] + '...' if self.token else None,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'is_active': self.is_active
        }

class Transaction(db.Model):
    """Bitcoin transaction model"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    txid = db.Column(db.String(255), unique=True, nullable=False, index=True)
    amount_btc = db.Column(db.Float, nullable=False)
    amount_usd = db.Column(db.Float, nullable=False)
    confirmations = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, credited
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    credited_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'txid': self.txid,
            'amount_btc': round(self.amount_btc, 8),
            'amount_usd': round(self.amount_usd, 2),
            'confirmations': self.confirmations,
            'status': self.status,
            'received_at': self.received_at.isoformat(),
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'credited_at': self.credited_at.isoformat() if self.credited_at else None
        }

class Deposit(db.Model):
    """User deposit aggregation model"""
    __tablename__ = 'deposits'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    total_btc = db.Column(db.Float, default=0.0)
    total_usd = db.Column(db.Float, default=0.0)
    credited_amount = db.Column(db.Float, default=0.0)  # Amount credited to balance
    status = db.Column(db.String(20), default='pending')  # pending, partial, credited
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    transaction_ids = db.Column(db.Text, default='')  # Comma-separated transaction IDs
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'total_btc': round(self.total_btc, 8),
            'total_usd': round(self.total_usd, 2),
            'credited_amount': round(self.credited_amount, 2),
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class CAPTCHASolve(db.Model):
    """CAPTCHA solve record model"""
    __tablename__ = 'captcha_solves'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    api_key = db.Column(db.String(128), db.ForeignKey('api_tokens.id'), nullable=False)
    website_url = db.Column(db.String(500), nullable=True)
    recaptcha_key = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    cost = db.Column(db.Float, default=0.001)
    solution = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    inference_time_ms = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'website_url': self.website_url,
            'recaptcha_key': self.recaptcha_key,
            'status': self.status,
            'cost': self.cost,
            'inference_time_ms': self.inference_time_ms,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class BitcoinAddress(db.Model):
    """Generated Bitcoin addresses for users"""
    __tablename__ = 'bitcoin_addresses'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True, unique=True)
    address = db.Column(db.String(255), unique=True, nullable=False, index=True)
    public_key = db.Column(db.String(255), nullable=True)
    private_key_encrypted = db.Column(db.Text, nullable=True)  # Store encrypted for security
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'address': self.address,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }
