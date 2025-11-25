#!/usr/bin/env python3
"""
WebSocket connection test script for pingping-server
Tests if the websocket server is running and responding correctly
"""

import asyncio
import json
import uuid
import websockets
import sys
import socket
import hmac
import base64
import hashlib
import time
from urllib.parse import urlencode

def generate_token(secret_key: str, client_id: str, device_id: str) -> str:
    """Generate authentication token using HMAC-SHA256"""
    ts = int(time.time())
    content = f"{client_id}|{device_id}|{ts}"
    sig = hmac.new(
        secret_key.encode("utf-8"), content.encode("utf-8"), hashlib.sha256
    ).digest()
    signature = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")
    token = f"{signature}.{ts}"
    return token

def check_port_open(host, port, timeout=2):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

async def test_websocket_connection(host="localhost", port=8000, path="/pingping/v1/", secret_key=None):
    """Test websocket connection to pingping-server"""
    
    # First check if port is open
    print(f"Checking if server is running on {host}:{port}...")
    if not check_port_open(host, port):
        print(f"✗ Port {port} is not open. Is the server running?")
        sys.exit(1)
    print(f"✓ Port {port} is open")
    
    # Generate test device-id and client-id
    device_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    
    # Build WebSocket URL with query parameters
    query_params = {
        "device-id": device_id,
        "client-id": client_id
    }
    
    # Add authorization token if secret_key is provided
    if secret_key:
        token = generate_token(secret_key, client_id, device_id)
        query_params["authorization"] = f"Bearer {token}"
        print(f"✓ Generated authentication token")
    
    ws_url = f"ws://{host}:{port}{path}?{urlencode(query_params)}"
    
    print(f"\nTesting WebSocket connection...")
    print(f"URL: {ws_url[:80]}...")
    print(f"Device-ID: {device_id}")
    print(f"Client-ID: {client_id}")
    if secret_key:
        print(f"Auth: Enabled (token provided)")
    else:
        print(f"Auth: Disabled (no secret key provided)")
    print("-" * 60)
    
    try:
        # Connect to WebSocket server with ping_interval to keep connection alive
        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as websocket:
            print("✓ WebSocket connection established!")
            
            # Create a message collector
            received_messages = []
            connection_closed = False
            
            async def message_collector():
                nonlocal connection_closed
                try:
                    while True:
                        try:
                            msg = await websocket.recv()
                            received_messages.append(('json', msg))
                        except websockets.exceptions.ConnectionClosed:
                            connection_closed = True
                            break
                        except Exception as e:
                            break
                except Exception:
                    pass
            
            # Start message collector
            collector_task = asyncio.create_task(message_collector())
            
            # Send hello message immediately
            print("\n[1] Sending 'hello' message...")
            hello_msg = {
                "type": "hello",
                "audio_params": {
                    "format": "pcm",
                    "sample_rate": 16000,
                    "channels": 1
                }
            }
            await websocket.send(json.dumps(hello_msg))
            print(f"✓ Sent hello message")
            
            # Wait a moment for responses
            await asyncio.sleep(2)
            
            # Check if we got a welcome/hello response
            if received_messages:
                print(f"\n✓ Received {len(received_messages)} message(s) after hello:")
                for i, (msg_type, msg) in enumerate(received_messages, 1):
                    try:
                        msg_json = json.loads(msg)
                        print(f"  [{i}] Type: {msg_json.get('type', 'unknown')}")
                        if msg_json.get('type') == 'hello' or 'session_id' in msg_json:
                            print(f"      Session ID: {msg_json.get('session_id', 'N/A')}")
                            if 'xiaozhi' in msg_json:
                                xz = msg_json.get('xiaozhi', {})
                                print(f"      Server: {xz.get('name', 'N/A')}")
                    except json.JSONDecodeError:
                        print(f"  [{i}] Binary data: {len(msg)} bytes")
                received_messages.clear()  # Clear for next test
            else:
                print("⚠ No response to hello message (connection may be closing)")
                if connection_closed:
                    print("✗ Connection was closed by server")
                    return
                print("  Continuing anyway...")
            
            # Test sending a "listen" message with text to trigger LLM conversation
            print("\nTesting 'listen' message to trigger LLM conversation...")
            listen_msg = {
                "type": "listen",
                "state": "detect",
                "text": "你好，请介绍一下你自己"
            }
            await websocket.send(json.dumps(listen_msg))
            print(f"✓ Sent listen message: {json.dumps(listen_msg)}")
            
            # Wait for multiple responses (stt, tts, llm, audio)
            print("Waiting for LLM responses (up to 15 seconds)...")
            responses_received = []
            max_responses = 20
            timeout_seconds = 15
            
            async def collect_responses():
                responses = []
                start_time = time.time()
                try:
                    while len(responses) < max_responses and (time.time() - start_time) < timeout_seconds:
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            responses.append(response)
                        except asyncio.TimeoutError:
                            # If we've received some responses, continue waiting
                            if len(responses) > 0:
                                continue
                            else:
                                break
                        except websockets.exceptions.ConnectionClosed:
                            break
                except Exception:
                    pass
                return responses
            
            responses_received = await collect_responses()
            
            if responses_received:
                print(f"\n✓ Received {len(responses_received)} response(s):")
                for i, response in enumerate(responses_received, 1):
                    try:
                        response_json = json.loads(response)
                        msg_type = response_json.get('type', 'unknown')
                        print(f"\n  [{i}] Type: {msg_type}")
                        
                        if msg_type == "stt":
                            print(f"      STT (Speech-to-Text): {response_json.get('text', 'N/A')}")
                        elif msg_type == "tts":
                            state = response_json.get('state', 'N/A')
                            print(f"      TTS state: {state}")
                            if 'text' in response_json:
                                print(f"      TTS text: {response_json.get('text', 'N/A')}")
                            if state == "stop":
                                print(f"      → TTS playback stopped")
                        elif msg_type == "llm":
                            print(f"      LLM Response: {response_json.get('text', 'N/A')}")
                            if 'emotion' in response_json:
                                print(f"      Emotion: {response_json.get('emotion', 'N/A')}")
                        elif msg_type == "audio":
                            print(f"      Audio control message")
                        else:
                            print(f"      Content: {str(response_json)[:150]}...")
                    except json.JSONDecodeError:
                        # Binary audio data
                        print(f"  [{i}] Binary audio data: {len(response)} bytes")
                
                # Check if we got a complete LLM response
                has_stt = any("stt" in str(r) for r in responses_received)
                has_tts_stop = any('"type":"tts"' in str(r) and '"state":"stop"' in str(r) for r in responses_received)
                
                if has_stt and has_tts_stop:
                    print("\n✓ LLM conversation completed successfully!")
                elif has_stt:
                    print("\n✓ LLM conversation started (STT received)")
            else:
                print("⚠ No responses received from LLM")
            
            # Test sending a "server" type message (like manager-api does)
            print("\nTesting 'server' message (update_config)...")
            server_msg = {
                "type": "server",
                "action": "update_config",
                "content": {
                    "secret": "test-secret"
                }
            }
            await websocket.send(json.dumps(server_msg))
            print(f"✓ Sent server message: {json.dumps(server_msg)}")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"✓ Received response: {response[:200]}...")
                try:
                    response_json = json.loads(response)
                    print(f"✓ Response is valid JSON")
                    print(f"  Type: {response_json.get('type', 'N/A')}")
                    print(f"  Status: {response_json.get('status', 'N/A')}")
                    print(f"  Message: {response_json.get('message', 'N/A')}")
                except json.JSONDecodeError:
                    print(f"  (Response is plain text)")
            except asyncio.TimeoutError:
                print("⚠ No response received within 5 seconds")
            
            print("\n" + "=" * 60)
            print("✓ WebSocket server is running correctly!")
            print("=" * 60)
            
    except websockets.exceptions.InvalidURI:
        print(f"✗ Invalid WebSocket URI: {ws_url}")
        sys.exit(1)
    except ConnectionRefusedError:
        print(f"✗ Connection refused. Is the server running on {host}:{port}?")
        sys.exit(1)
    except websockets.exceptions.ConnectionClosed as e:
        print(f"✗ Connection closed: {e.code} - {e.reason}")
        if e.code == 1000:
            print("  (Connection closed normally - may need authentication)")
        sys.exit(1)
    except Exception as e:
        error_type = type(e).__name__
        if "InvalidStatusCode" in error_type:
            print(f"✗ Connection failed with status code")
        else:
            print(f"✗ Connection error: {error_type}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test WebSocket connection to pingping-server")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--path", default="/pingping/v1/", help="WebSocket path (default: /pingping/v1/)")
    parser.add_argument("--secret", help="Secret key for authentication (optional)")
    
    args = parser.parse_args()
    
    asyncio.run(test_websocket_connection(args.host, args.port, args.path, args.secret))

