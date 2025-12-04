#!/usr/bin/env python3
"""
Test script to verify Java API returns agent info correctly
"""
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import httpx
    USE_HTTPX = True
except ImportError:
    try:
        import requests
        USE_HTTPX = False
    except ImportError:
        print("Error: Need either 'httpx' or 'requests' library")
        sys.exit(1)

# Configuration - adjust these based on your setup
JAVA_API_URL = "http://localhost:8002/pingping"  # Adjust if different
API_SECRET = "your-secret-here"  # You'll need to get this from config
DEVICE_MAC = "A3:75:24:79:8F:1D"
CLIENT_ID = "A3:75:24:79:8F:1D"

def test_agent_models_api():
    """Test the /config/agent-models endpoint"""
    
    url = f"{JAVA_API_URL}/config/agent-models"
    
    payload = {
        "macAddress": DEVICE_MAC,
        "clientId": CLIENT_ID,
        "selectedModule": {
            "VAD": None,
            "ASR": None,
            "TTS": None,
            "LLM": None,
            "Memory": None,
            "Intent": None
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {API_SECRET}"
    }
    
    print(f"Testing Java API endpoint: {url}")
    print(f"Device MAC: {DEVICE_MAC}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 80)
    
    try:
        if USE_HTTPX:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload, headers=headers)
        else:
            response = requests.post(url, json=payload, headers=headers, timeout=30.0)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print("-" * 80)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # Check if agent info is in the response
            if result.get("code") == 0:
                data = result.get("data", {})
                if "agent" in data:
                    agent_info = data["agent"]
                    print("\n✅ SUCCESS: Agent info found in response!")
                    print(f"   Agent ID: {agent_info.get('id')}")
                    print(f"   Agent Name: {agent_info.get('name')}")
                else:
                    print("\n❌ PROBLEM: No 'agent' field in response data")
                    print(f"   Available keys: {list(data.keys())}")
            else:
                print(f"\n❌ API returned error: {result.get('msg')}")
                print(f"   Error code: {result.get('code')}")
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except (httpx.ConnectError if USE_HTTPX else requests.exceptions.ConnectionError) as e:
        print(f"\n❌ Connection Error: Could not connect to {url}")
        print(f"   Make sure the Java API server is running")
        print(f"   Error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Try to get API secret from config if available
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), "data", ".config.yaml")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                manager_api = config.get("manager-api", {})
                if manager_api.get("url"):
                    JAVA_API_URL = manager_api["url"].rstrip("/")
                if manager_api.get("secret"):
                    API_SECRET = manager_api["secret"]
                    print(f"Loaded config from {config_path}")
                    print(f"API URL: {JAVA_API_URL}")
                    print(f"API Secret: {'*' * len(API_SECRET) if API_SECRET else 'NOT SET'}")
                    print("-" * 80)
    except Exception as e:
        print(f"Could not load config: {e}")
        print("Using default values. Please set JAVA_API_URL and API_SECRET in the script.")
        print("-" * 80)
    
    if API_SECRET == "your-secret-here":
        print("⚠️  WARNING: Please set API_SECRET in the script or configure manager-api in data/.config.yaml")
        print("   You can find the secret in your manager-api configuration")
        sys.exit(1)
    
    test_agent_models_api()

