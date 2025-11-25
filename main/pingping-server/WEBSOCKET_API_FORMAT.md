# PingPing WebSocket API Request Format

Based on online documentation and codebase analysis, here is the expected WebSocket API request format for the pingping-esp32-server project.

## Connection Establishment

### WebSocket URL
```
ws://<server-ip>:<port>/pingping/v1/
```
- Default port: `8000`
- Path: `/pingping/v1/`

### Connection Headers (Optional - can be in query params)
When establishing the WebSocket connection, you can include:

**Via HTTP Headers:**
- `Authorization`: `Bearer <access_token>` (if authentication enabled)
- `Device-ID`: `<device_id>` (UUID or MAC address)
- `Client-ID`: `<client_id>` (UUID)

**Via Query Parameters:**
```
ws://server:8000/pingping/v1/?device-id=<uuid>&client-id=<uuid>&authorization=Bearer+<token>
```

## Message Types

### 1. Hello Message (Initialization)

**Client → Server:**
```json
{
  "type": "hello",
  "audio_params": {
    "format": "opus" | "pcm",
    "sample_rate": 16000,
    "channels": 1,
    "frame_duration": 60
  },
  "features": {
    "mcp": true  // Optional: indicates MCP support
  }
}
```

**Server → Client Response:**
```json
{
  "type": "hello",
  "version": 1,
  "transport": "websocket",
  "audio_params": {
    "format": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_duration": 60
  },
  "session_id": "<unique_session_id>",
  "pingping": {
    "name": "pingping-esp32-server",
    "type": "hello",
    "version": 1
  }
}
```

### 2. Listen Message (Trigger LLM Conversation)

**Client → Server:**
```json
{
  "type": "listen",
  "state": "detect",
  "text": "你好，请介绍一下你自己",
  "mode": "auto"  // Optional: "auto" | "manual"
}
```

**Alternative formats:**
- Start listening: `{"type": "listen", "state": "start"}`
- Stop listening: `{"type": "listen", "state": "stop"}`
- Detect with text: `{"type": "listen", "state": "detect", "text": "your text here"}`

**Server → Client Responses:**
- **STT (Speech-to-Text) confirmation:**
  ```json
  {
    "type": "stt",
    "text": "你好，请介绍一下你自己",
    "session_id": "<session_id>"
  }
  ```

- **TTS (Text-to-Speech) status:**
  ```json
  {
    "type": "tts",
    "state": "start" | "sentence_start" | "stop",
    "text": "你好",  // Optional, present in sentence_start
    "session_id": "<session_id>"
  }
  ```

- **LLM Response (if emotion detection enabled):**
  ```json
  {
    "type": "llm",
    "text": "😊",
    "emotion": "happy",
    "session_id": "<session_id>"
  }
  ```

- **Binary Audio Data:** Opus-encoded audio packets (sent as binary WebSocket frames)

### 3. Abort Message (Interrupt Current Response)

**Client → Server:**
```json
{
  "type": "abort"
}
```

### 4. Server Action Messages (from Manager-API)

**Client → Server:**
```json
{
  "type": "server",
  "action": "update_config" | "restart",
  "content": {
    "secret": "<server_secret_key>"
  }
}
```

**Server → Client Response:**
```json
{
  "type": "server",
  "status": "success" | "error",
  "message": "配置更新成功",
  "content": {
    "action": "update_config"
  }
}
```

### 5. MCP (Model Context Protocol) Messages

**Client → Server:**
```json
{
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list" | "tools/call",
    "params": {
      "name": "tool_name",
      "arguments": {}
    }
  }
}
```

### 6. IOT Messages

**Client → Server:**
```json
{
  "type": "iot",
  "action": "<action>",
  "params": {}
}
```

## Audio Data Transmission

### Binary Audio Frames
- **Format:** Opus-encoded audio
- **Sample Rate:** 16000 Hz (default, can be configured)
- **Channels:** 1 (mono)
- **Frame Duration:** 60ms (default)
- **Transmission:** Sent as binary WebSocket frames (not JSON)

## Complete Communication Flow

### Example: LLM Conversation

1. **Connect to WebSocket:**
   ```
   ws://localhost:8000/pingping/v1/?device-id=<uuid>&client-id=<uuid>
   ```

2. **Send Hello:**
   ```json
   {"type": "hello", "audio_params": {"format": "pcm", "sample_rate": 16000, "channels": 1}}
   ```

3. **Receive Welcome:**
   ```json
   {"type": "hello", "session_id": "...", "pingping": {...}}
   ```

4. **Send Listen with Text:**
   ```json
   {"type": "listen", "state": "detect", "text": "你好"}
   ```

5. **Receive Responses:**
   - STT message (confirms input)
   - TTS start message
   - Binary audio data (streaming)
   - TTS stop message (conversation complete)

## Authentication

If `server.auth.enabled: true` in config:

1. Generate token using HMAC-SHA256:
   ```
   token = HMAC-SHA256(client_id|device_id|timestamp, secret_key)
   token_string = base64_encode(signature) + "." + timestamp
   ```

2. Include in connection:
   - Header: `Authorization: Bearer <token>`
   - Or query param: `authorization=Bearer+<token>`

## Error Handling

- **Connection Closed:** Server may close connection with code 1000 (normal) or other codes (error)
- **Invalid Messages:** Server may ignore or return error messages
- **Timeout:** Server may close idle connections after timeout period

## References

- Official Documentation: https://xiaozhi.dev/en/docs/development/websocket/
- Protocol Details: https://deepwiki.com/wanghongli123a/py-xiaozhi/3.1-websocket-protocol
- GitHub Repository: https://github.com/xinnan-tech/xiaozhi-esp32-server

## Notes

- All JSON messages should be sent as text frames
- Audio data should be sent as binary frames
- Session ID from hello response should be included in subsequent messages
- The server processes messages asynchronously
- Multiple message types can be received in sequence during a conversation

