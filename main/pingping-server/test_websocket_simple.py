#!/usr/bin/env python3
"""
Simple WebSocket test - demonstrates the expected message flow for LLM conversations
"""

import asyncio
import json
import uuid
import websockets
import sys
from urllib.parse import urlencode

async def test_llm_conversation(host="localhost", port=8000):
    """Test LLM conversation flow"""
    
    device_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    
    query_params = {
        "device-id": device_id,
        "client-id": client_id
    }
    ws_url = f"ws://{host}:{port}/pingping/v1/?{urlencode(query_params)}"
    
    print("=" * 70)
    print("WebSocket LLM Conversation Test")
    print("=" * 70)
    print(f"URL: {ws_url[:80]}...")
    print(f"Device-ID: {device_id}")
    print(f"Client-ID: {client_id}")
    print("-" * 70)
    
    try:
        async with websockets.connect(ws_url, ping_interval=None) as websocket:
            print("\n[STEP 1] Connection established")
            
            # Step 2: Send hello
            print("\n[STEP 2] Sending 'hello' message...")
            hello_msg = {
                "type": "hello",
                "audio_params": {
                    "format": "pcm",
                    "sample_rate": 16000,
                    "channels": 1
                }
            }
            await websocket.send(json.dumps(hello_msg))
            print(f"  ✓ Sent: {json.dumps(hello_msg, ensure_ascii=False)}")
            
            # Step 3: Wait for welcome/hello response
            print("\n[STEP 3] Waiting for server response...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                try:
                    resp_json = json.loads(response)
                    print(f"  ✓ Received: type={resp_json.get('type')}, session_id={resp_json.get('session_id', 'N/A')}")
                except:
                    print(f"  ✓ Received: {response[:100]}")
            except asyncio.TimeoutError:
                print("  ⚠ No response (connection may have closed)")
                return
            
            # Step 4: Send listen message to trigger LLM
            print("\n[STEP 4] Sending 'listen' message to trigger LLM conversation...")
            listen_msg = {
                "type": "listen",
                "state": "detect",
                "text": "Hello, please introduce yourself briefly"
            }
            await websocket.send(json.dumps(listen_msg))
            print(f"  ✓ Sent: {json.dumps(listen_msg, ensure_ascii=False)}")
            
            # Step 5: Collect LLM responses
            print("\n[STEP 5] Collecting LLM responses (15 second timeout)...")
            responses = []
            start_time = asyncio.get_event_loop().time()
            timeout = 15.0
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    responses.append(msg)
                    
                    # Check if message is binary (audio data) or text (JSON)
                    if isinstance(msg, bytes):
                        # Binary audio data
                        print(f"\n  🎵 Audio: {len(msg)} bytes (binary Opus data)")
                        continue
                    
                    # Try to parse as JSON
                    try:
                        msg_json = json.loads(msg)
                        msg_type = msg_json.get('type', 'unknown')
                        
                        if msg_type == "stt":
                            print(f"\n  📝 STT: {msg_json.get('text', 'N/A')}")
                        elif msg_type == "tts":
                            state = msg_json.get('state', 'N/A')
                            text = msg_json.get('text', '')
                            print(f"\n  🔊 TTS: state={state}" + (f", text={text}" if text else ""))
                            if state == "stop":
                                print("  → Conversation complete!")
                                break
                        elif msg_type == "llm":
                            print(f"\n  🤖 LLM: {msg_json.get('text', 'N/A')}")
                        else:
                            print(f"\n  📨 {msg_type}: {str(msg_json)[:80]}...")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Binary audio data received as string (shouldn't happen, but handle it)
                        print(f"\n  🎵 Audio: {len(msg)} bytes (binary data)")
                        
                except asyncio.TimeoutError:
                    if len(responses) > 0:
                        continue
                    else:
                        break
                except websockets.exceptions.ConnectionClosed:
                    print("\n  ✗ Connection closed by server")
                    break
            
            # Summary
            print("\n" + "=" * 70)
            print("Test Summary")
            print("=" * 70)
            print(f"Total responses received: {len(responses)}")
            
            if len(responses) > 0:
                print("\n✓ SUCCESS: Received responses from server!")
                print("\nResponse types received:")
                for msg in responses:
                    try:
                        msg_json = json.loads(msg)
                        print(f"  - {msg_json.get('type', 'unknown')}")
                    except:
                        print(f"  - binary audio")
            else:
                print("\n⚠ WARNING: No responses received")
                print("\nPossible reasons:")
                print("  1. Server requires authentication (check server.auth.enabled)")
                print("  2. Server is closing connections immediately")
                print("  3. LLM module is not configured or initialized")
                print("  4. Check server logs for errors")
            
            print("=" * 70)
            
    except ConnectionRefusedError:
        print(f"\n✗ ERROR: Connection refused. Is the server running on {host}:{port}?")
        sys.exit(1)
    except websockets.exceptions.ConnectionClosed as e:
        print(f"\n✗ ERROR: Connection closed: {e.code} - {e.reason}")
        print("\nThis usually means:")
        print("  - Authentication failed (if auth is enabled)")
        print("  - Server rejected the connection")
        print("  - Check server configuration and logs")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test WebSocket LLM conversation")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    args = parser.parse_args()
    
    asyncio.run(test_llm_conversation(args.host, args.port))

