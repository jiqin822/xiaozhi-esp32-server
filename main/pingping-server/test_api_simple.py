#!/usr/bin/env python3
"""
Simple test to verify Java API returns agent info
Uses the same config loading as the main server
"""
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config_loader import load_config
from config.manage_api_client import ManageApiClient, get_agent_models

def test_api():
    print("Loading configuration...")
    try:
        config = load_config()
        print("✅ Config loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # Check if manager-api is configured
    manager_api = config.get("manager-api")
    if not manager_api:
        print("❌ manager-api not configured in config file")
        print("   Please add manager-api section to data/.config.yaml")
        return
    
    print(f"✅ Manager API URL: {manager_api.get('url')}")
    print(f"✅ Manager API Secret: {'*' * len(manager_api.get('secret', ''))}")
    print("-" * 80)
    
    # Initialize API client
    try:
        ManageApiClient(config)
        print("✅ API client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize API client: {e}")
        return
    
    # Test with device MAC
    device_mac = "A3:75:24:79:8F:1D"
    client_id = "A3:75:24:79:8F:1D"
    
    print(f"\nTesting with device MAC: {device_mac}")
    print("-" * 80)
    
    try:
        selected_module = config.get("selected_module", {})
        result = get_agent_models(device_mac, client_id, selected_module)
        
        if result:
            print("✅ API call successful!")
            print(f"\nResponse keys: {list(result.keys())}")
            
            # Check for agent info
            if "agent" in result:
                agent_info = result["agent"]
                print("\n✅ SUCCESS: Agent info found in response!")
                print(f"   Agent ID: {agent_info.get('id')}")
                print(f"   Agent Name: {agent_info.get('name')}")
            else:
                print("\n❌ PROBLEM: No 'agent' field in response")
                print(f"   Available keys: {list(result.keys())}")
                print(f"\nFull response (first 1000 chars):")
                print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])
        else:
            print("❌ API returned None/empty response")
            
    except Exception as e:
        print(f"❌ API call failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api()

