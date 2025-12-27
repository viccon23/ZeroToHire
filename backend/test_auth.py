"""
Simple authentication test server - tests auth system without LLM dependencies
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from database import Database
from auth import AuthManager, token_required, optional_token, validate_password, validate_email, validate_username
import os

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize database
db = Database()
auth_manager = AuthManager()

# Authentication Routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Validate input
        if not username or not email or not password:
            return jsonify({'error': 'Missing required fields'}), 400
        
        if not validate_username(username):
            return jsonify({'error': 'Invalid username format'}), 400
            
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
            
        if not validate_password(password):
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        # Check if user already exists
        if db.get_user_by_username(username):
            return jsonify({'error': 'Username already exists'}), 409
            
        if db.get_user_by_email(email):
            return jsonify({'error': 'Email already exists'}), 409
        
        # Create user
        password_hash = auth_manager.hash_password(password)
        user_id = db.create_user(username, email, password_hash)
        
        # Generate tokens
        access_token = auth_manager.create_access_token(user_id, username)
        refresh_token = auth_manager.create_refresh_token(user_id, username)
        
        user = db.get_user_by_id(user_id)
        
        return jsonify({
            'message': 'User registered successfully',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email']
            },
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Missing username or password'}), 400
        
        user = db.get_user_by_username(username)
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not auth_manager.verify_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Generate tokens
        access_token = auth_manager.create_access_token(user['id'], user['username'])
        refresh_token = auth_manager.create_refresh_token(user['id'], user['username'])
        
        # Update last login
        db.update_user_last_login(user['id'])
        
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email']
            },
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    try:
        user = db.get_user_by_id(current_user['id'])
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user statistics
        stats = db.get_user_statistics(current_user['id'])
        
        return jsonify({
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'created_at': user['created_at'],
                'last_login': user['last_login']
            },
            'statistics': stats
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test', methods=['GET'])
@optional_token
def test_optional(current_user):
    """Test endpoint that works with or without authentication"""
    if current_user:
        return jsonify({
            'message': f'Hello, {current_user["username"]}! (Authenticated)',
            'authenticated': True,
            'user_id': current_user['id']
        }), 200
    else:
        return jsonify({
            'message': 'Hello, Guest! (Not authenticated)',
            'authenticated': False
        }), 200

if __name__ == '__main__':
    print("🔐 Authentication Test Server")
    print("=" * 50)
    print(f"Server running on http://{os.getenv('FLASK_HOST', '127.0.0.1')}:{os.getenv('FLASK_PORT', 5000)}")
    print("\nAvailable endpoints:")
    print("  POST /api/auth/register - Register new user")
    print("  POST /api/auth/login    - Login user")
    print("  GET  /api/auth/profile  - Get user profile (requires auth)")
    print("  GET  /api/test          - Test optional auth")
    print("=" * 50)
    
    app.run(
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=True
    )
