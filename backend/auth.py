"""
Authentication utilities for ZeroToHire.
Handles password hashing, JWT token generation/verification, and user session management.
"""

import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict
from functools import wraps
from flask import request, jsonify
import os


# Secret key for JWT
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


class AuthManager:
    """Manages authentication operations."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    @staticmethod
    def create_access_token(user_id: int, username: str) -> str:
        """Create a JWT access token."""
        expiration = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': expiration,
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    @staticmethod
    def create_refresh_token(user_id: int, username: str) -> str:
        """Create a JWT refresh token."""
        expiration = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            'user_id': user_id,
            'username': username,
            'exp': expiration,
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    @staticmethod
    def verify_token(token: str, token_type: str = 'access') -> Optional[Dict]:
        """
        Verify a JWT token and return the payload.
        Returns None if token is invalid or expired.
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            # Check token type
            if payload.get('type') != token_type:
                return None
            
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def get_token_from_request() -> Optional[str]:
        """Extract JWT token from request headers."""
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header.split(' ')[1]
        return None


def token_required(f):
    """
    Decorator to protect routes that require authentication.
    Adds 'current_user' to kwargs with user_id and username.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = AuthManager.get_token_from_request()
        
        if not token:
            return jsonify({'error': 'Authentication token is missing'}), 401
        
        payload = AuthManager.verify_token(token, 'access')
        
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Add user info to kwargs
        kwargs['current_user'] = {
            'user_id': payload['user_id'],
            'username': payload['username']
        }
        
        return f(*args, **kwargs)
    
    return decorated


def optional_token(f):
    """
    Decorator for routes where authentication is optional.
    Adds 'current_user' to kwargs if authenticated, otherwise None.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = AuthManager.get_token_from_request()
        
        if token:
            payload = AuthManager.verify_token(token, 'access')
            if payload:
                kwargs['current_user'] = {
                    'user_id': payload['user_id'],
                    'username': payload['username']
                }
            else:
                kwargs['current_user'] = None
        else:
            kwargs['current_user'] = None
        
        return f(*args, **kwargs)
    
    return decorated


def validate_password(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password strength.
    Returns (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    return True, None


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username: str) -> tuple[bool, Optional[str]]:
    """
    Validate username.
    Returns (is_valid, error_message).
    """
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    
    if len(username) > 30:
        return False, "Username must be no more than 30 characters"
    
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    
    return True, None
