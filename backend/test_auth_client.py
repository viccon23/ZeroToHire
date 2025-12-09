"""
Test Authentication System
Tests the authentication endpoints with actual HTTP requests
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000/api/auth"

def print_response(title, response):
    """Print formatted response"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")

def test_authentication():
    """Run authentication tests"""
    
    # Test 1: Register a new user
    print("\n🔐 Testing Authentication System")
    print("="*60)
    
    register_data = {
        "username": "testuser2",
        "email": "test2@example.com",
        "password": "TestPass123!"
    }
    
    print("\n1. Testing User Registration...")
    response = requests.post(f"{BASE_URL}/register", json=register_data)
    print_response("Registration Response", response)
    
    if response.status_code == 201:
        data = response.json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        print(f"\n✅ Registration successful!")
        print(f"Access Token (first 50 chars): {access_token[:50]}...")
        print(f"Refresh Token (first 50 chars): {refresh_token[:50]}...")
        
        # Test 2: Login with the same credentials
        print("\n\n2. Testing User Login...")
        login_data = {
            "username": "testuser",
            "password": "TestPass123!"
        }
        response = requests.post(f"{BASE_URL}/login", json=login_data)
        print_response("Login Response", response)
        
        if response.status_code == 200:
            print("\n✅ Login successful!")
            
            # Test 3: Access protected profile endpoint
            print("\n\n3. Testing Protected Endpoint (Profile)...")
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{BASE_URL}/profile", headers=headers)
            print_response("Profile Response", response)
            
            if response.status_code == 200:
                print("\n✅ Protected endpoint access successful!")
                
            # Test 4: Test without token (should fail)
            print("\n\n4. Testing Protected Endpoint Without Token...")
            response = requests.get(f"{BASE_URL}/profile")
            print_response("Profile Response (No Token)", response)
            
            if response.status_code == 401:
                print("\n✅ Correctly rejected unauthorized access!")
            
            # Test 5: Test optional auth endpoint
            print("\n\n5. Testing Optional Auth Endpoint...")
            
            # Without token
            response = requests.get("http://127.0.0.1:5000/api/test")
            print_response("Test Endpoint (No Token)", response)
            
            # With token
            response = requests.get("http://127.0.0.1:5000/api/test", headers=headers)
            print_response("Test Endpoint (With Token)", response)
            
            print("\n\n" + "="*60)
            print("🎉 All Authentication Tests Completed!")
            print("="*60)
    else:
        print("\n❌ Registration failed. Tests aborted.")
        if response.status_code == 400:
            print("This might be because the user already exists.")
            print("To reset, delete backend/backend.db and try again.")

if __name__ == "__main__":
    try:
        # Check if server is running
        response = requests.get("http://127.0.0.1:5000/api/test", timeout=2)
        test_authentication()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Test server is not running!")
        print("\nPlease start the server first:")
        print("  cd backend")
        print("  python test_auth.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")
