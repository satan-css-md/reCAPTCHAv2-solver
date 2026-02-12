import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///captcha_service.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    
    # CAPTCHA Settings
    CAPTCHA_PRICE = 0.001  # $0.001 per captcha
    MIN_DEPOSIT = 15.0  # $15 minimum deposit
    
    # Bitcoin Settings
    BITCOIN_NETWORK = 'testnet'  # Use 'testnet' for testing, 'mainnet' for production
    CONFIRMATION_THRESHOLD = 2  # Number of confirmations required
    BITCOIN_PRICE_API = 'https://api.coindesk.com/v1/bpi/currentprice/BTC.json'
    
    # API Settings
    API_RATE_LIMIT = "100 per hour"
    
class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
