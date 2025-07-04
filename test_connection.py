import requests
import json

def test_server_connection():
    """Test if Django server is accessible"""
    server_url = "http://192.168.100.5:8000"  # Replace with your server IP
    
    try:
        # Test basic connection
        response = requests.get(f"{server_url}/api/images/", timeout=5)
        
        if response.status_code == 200:
            print("✓ Server connection successful!")
            result = response.json()
            print(f"Found {len(result['images'])} images in database")
            return True
        else:
            print(f"✗ Server responded with error: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Check:")
        print("  - Server is running (python manage.py runserver 0.0.0.0:8000)")
        print("  - IP address is correct")
        print("  - Both devices are on same network")
        return False
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    test_server_connection()
