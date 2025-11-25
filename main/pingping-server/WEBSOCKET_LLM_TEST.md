# WebSocket LLM Conversation Testing Guide

## Overview
This guide explains how to trigger and receive LLM conversation responses via WebSocket.

## Connection Setup

### 1. WebSocket URL Format
```
ws://<host>:<port>/pingping/v1/?device-id=<uuid>&client-id=<uuid>
```

### 2. Required Headers/Query Parameters
- `device-id`: UUID string (can be in query params or headers)
- `client-id`: UUID string (optional, can be in query params or headers)
- `authorization`: Bearer token (required if `server.auth.enabled` is `true`)

## Message Types

### 1. Hello Message (Initialization)
Send this first to initialize the connection:

```json
{
  "type": "hello",
  "audio_params": {
    "format": "pcm",
    "sample_rate": 16000,
    "channels": 1
  }
}
```

**Response:** Server sends back a welcome message with session information.

### 2. Listen Message (Trigger LLM Conversation)
To trigger an LLM conversation, send a "listen" message with state "detect" and text:

```json
{
  "type": "listen",
  "state": "detect",
  "text": "你好，请介绍一下你自己"
}
```

**Alternative format with speaker information:**
```json
{
  "type": "listen",
  "state": "detect",
  "text": "{\"speaker\": \"user1\", \"content\": \"你好\"}"
}
```

## Response Messages

After sending a "listen" message, you'll receive multiple response types:

### 1. STT (Speech-to-Text) Message
Confirms the text was received:
```json
{
  "type": "stt",
  "text": "你好，请介绍一下你自己",
  "session_id": "<session_id>"
}
```

### 2. TTS (Text-to-Speech) Messages
Status updates for TTS processing:
```json
{
  "type": "tts",
  "state": "start",
  "session_id": "<session_id>"
}
```

```json
{
  "type": "tts",
  "state": "sentence_start",
  "text": "你好",
  "session_id": "<session_id>"
}
```

```json
{
  "type": "tts",
  "state": "stop",
  "session_id": "<session_id>"
}
```

### 3. LLM Response Messages
LLM text responses (if emotion detection is enabled):
```json
{
  "type": "llm",
  "text": "😊",
  "emotion": "happy",
  "session_id": "<session_id>"
}
```

### 4. Binary Audio Data
Opus-encoded audio packets (sent as binary data, not JSON)

## Complete Flow Example

1. **Connect to WebSocket**
   ```
   ws://localhost:8000/pingping/v1/?device-id=123&client-id=456
   ```

2. **Send Hello Message**
   ```json
   {"type": "hello", "audio_params": {"format": "pcm", "sample_rate": 16000, "channels": 1}}
   ```

3. **Wait for Welcome Message**
   Server responds with session information.

4. **Send Listen Message**
   ```json
   {"type": "listen", "state": "detect", "text": "你好"}
   ```

5. **Receive Responses**
   - STT message (confirms input)
   - TTS start message
   - Binary audio data (Opus packets)
   - TTS stop message (conversation complete)

## Notes

- The LLM response text is typically sent via TTS messages, not separate "llm" type messages
- Binary audio data contains the actual speech output
- The conversation is complete when you receive a TTS message with `state: "stop"`
- If authentication is enabled, you must provide a valid Bearer token in the Authorization header

## Testing

Use the provided test script:
```bash
python3 test_websocket.py
```

Or with authentication:
```bash
python3 test_websocket.py --secret "your-secret-key"
```

