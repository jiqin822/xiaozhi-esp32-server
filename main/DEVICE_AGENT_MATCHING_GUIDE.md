# Device-Agent Matching and Voice Recording Guide

## How Device-Agent Matching Works

### 1. Connection Flow

When a device connects to the WebSocket server:

1. **Device sends connection request** with `device-id` header (MAC address)
   - Example: `device-id: AA:BB:CC:DD:EE:FF`
   - Can also be passed as query parameter: `?device-id=AA:BB:CC:DD:EE:FF`

2. **Server extracts device-id** from headers:
   ```python
   # pingping-server/core/connection.py line 182
   self.device_id = self.headers.get("device-id", None)
   ```

3. **Server calls Java API** to get agent configuration:
   ```python
   # pingping-server/core/connection.py line 532-536
   private_config = get_private_config_from_api(
       self.config,
       self.headers.get("device-id"),  # MAC address
       self.headers.get("client-id", self.headers.get("device-id")),
   )
   ```

4. **Java API looks up device** by MAC address:
   ```java
   // manager-api/src/main/java/pingping/modules/config/service/impl/ConfigServiceImpl.java
   DeviceEntity device = deviceService.getDeviceByMacAddress(macAddress);
   String agentId = device.getAgentId();  // Get agent ID from device
   AgentEntity agent = agentService.getAgentById(agentId);  // Get agent config
   ```

### 2. Common Issues

#### Issue 1: Always Using Default Agent

**Problem**: Device is not bound to an agent, or device-id is incorrect.

**Solutions**:

1. **Check device binding**:
   - Go to Device Management in the web UI
   - Ensure device is bound to the correct agent
   - Binding endpoint: `POST /device/bind/{agentId}/{deviceCode}`

2. **Verify device-id header**:
   - Check that your device/client sends the correct MAC address in `device-id` header
   - MAC address format: `AA:BB:CC:DD:EE:FF` or `AA_BB_CC_DD_EE_FF`
   - The MAC address must match exactly what's stored in the database

3. **Check device registration**:
   - Device must be registered first via `POST /device/register`
   - Then activated/bound via `POST /device/bind/{agentId}/{deviceCode}`

4. **Verify in database**:
   ```sql
   -- Check if device exists and is bound to an agent
   SELECT id, mac_address, agent_id, user_id 
   FROM ai_device 
   WHERE mac_address = 'AA:BB:CC:DD:EE:FF';
   ```

#### Issue 2: Device Not Found Error

If you see `DeviceNotFoundException`, the device is not registered or bound.

**Fix**:
1. Register device: `POST /device/register` with MAC address
2. Get activation code from response
3. Bind device: `POST /device/bind/{agentId}/{activationCode}`

### 3. Debugging Steps

1. **Check WebSocket connection headers**:
   ```javascript
   // In test_page.html or your client
   const ws = new WebSocket('ws://localhost:8000?device-id=AA:BB:CC:DD:EE:FF');
   ```

2. **Check server logs**:
   ```
   # Look for these log messages in pingping-server logs:
   "获取差异化配置成功" - Successfully got agent config
   "获取差异化配置失败" - Failed to get agent config
   "设备绑定异常" - Device binding error
   ```

3. **Check Java API logs**:
   ```
   # Look for device lookup in manager-api logs
   # Check ConfigServiceImpl.getAgentModels() method
   ```

4. **Verify device-agent binding**:
   ```bash
   # Check via API
   curl -X GET "http://localhost:8002/device/bind/{agentId}" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

## Voice Recording Storage and Retrieval

### 1. How Voice Recordings Are Stored

Voice recordings are stored in two places:

1. **Audio data** in `ai_agent_chat_audio` table:
   ```sql
   CREATE TABLE ai_agent_chat_audio (
       id VARCHAR(32) PRIMARY KEY,  -- audio_id
       audio LONGBLOB  -- Opus audio data
   );
   ```

2. **Chat history** in `ai_agent_chat_history` table:
   ```sql
   CREATE TABLE ai_agent_chat_history (
       id BIGINT PRIMARY KEY,
       mac_address VARCHAR(50),
       agent_id VARCHAR(32),
       session_id VARCHAR(50),
       chat_type TINYINT,  -- 1=user, 2=agent
       content VARCHAR(1024),  -- Text content
       audio_id VARCHAR(32),  -- Reference to ai_agent_chat_audio.id
       created_at DATETIME
   );
   ```

### 2. How to Retrieve Voice Recordings

#### Method 1: Via API Endpoints

1. **Get chat history** (includes audio_id):
   ```bash
   GET /agent/{agentId}/chat-history/user
   ```
   Response includes `audio_id` for messages with audio.

2. **Get audio download ID**:
   ```bash
   POST /agent/audio/{audioId}
   ```
   Returns a temporary UUID for downloading.

3. **Download audio**:
   ```bash
   GET /agent/play/{uuid}
   ```
   Returns the audio file (Opus format).

#### Method 2: Direct Database Query

```sql
-- Get chat history with audio IDs
SELECT 
    ch.id,
    ch.mac_address,
    ch.agent_id,
    ch.session_id,
    ch.chat_type,
    ch.content,
    ch.audio_id,
    ch.created_at,
    CASE 
        WHEN ch.audio_id IS NOT NULL THEN 'Yes'
        ELSE 'No'
    END as has_audio
FROM ai_agent_chat_history ch
WHERE ch.agent_id = 'YOUR_AGENT_ID'
ORDER BY ch.created_at DESC;

-- Get audio data
SELECT id, LENGTH(audio) as audio_size_bytes
FROM ai_agent_chat_audio
WHERE id = 'AUDIO_ID';
```

### 3. Common Issues with Voice Recordings

#### Issue 1: No Audio Recordings Found

**Possible causes**:

1. **Chat history configuration**:
   - Check `chatHistoryConf` in agent configuration:
     - `0` = No recording
     - `1` = Text only
     - `2` = Text and audio
   - Audio is only saved if `chatHistoryConf = 2`

2. **Audio not being reported**:
   - Check if `report_tts_enable` is enabled in connection
   - Audio is saved via `report()` function in `pingping-server/core/handle/reportHandle.py`

3. **Check agent configuration**:
   ```java
   // In AgentEntity
   private Integer chatHistoryConf;  // Must be 2 for audio recording
   ```

#### Issue 2: Audio ID Not in Chat History

**Check**:
```sql
-- Find messages with audio
SELECT * FROM ai_agent_chat_history 
WHERE audio_id IS NOT NULL 
AND agent_id = 'YOUR_AGENT_ID';
```

If no results, audio reporting might be disabled or failing.

### 4. Enabling Voice Recording

1. **Set agent chat history config**:
   ```java
   // In AgentEntity or via API
   agent.setChatHistoryConf(2);  // 2 = Text and audio
   ```

2. **Verify reporting is enabled**:
   ```python
   # In pingping-server/core/connection.py
   self.report_tts_enable = self.read_config_from_api  # Must be True
   ```

3. **Check reporting thread**:
   ```python
   # Reporting thread must be started
   self._init_report_threads()  # Called during initialization
   ```

### 5. Testing Voice Recording

1. **Send audio message** via WebSocket
2. **Check chat history**:
   ```bash
   curl -X GET "http://localhost:8002/agent/{agentId}/chat-history/user" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
3. **Verify audio_id** is present in response
4. **Download audio**:
   ```bash
   # Step 1: Get download UUID
   curl -X POST "http://localhost:8002/agent/audio/{audioId}" \
     -H "Authorization: Bearer YOUR_TOKEN"
   
   # Step 2: Download audio
   curl -X GET "http://localhost:8002/agent/play/{uuid}" \
     --output audio.opus
   ```

## Troubleshooting Checklist

### Device-Agent Matching

- [ ] Device is registered in database (`ai_device` table)
- [ ] Device has `agent_id` set (not NULL)
- [ ] `device-id` header matches MAC address in database exactly
- [ ] Device is bound to correct agent via `/device/bind/{agentId}/{deviceCode}`
- [ ] Java API is accessible and responding
- [ ] Check server logs for "获取差异化配置成功" message

### Voice Recordings

- [ ] Agent `chatHistoryConf` is set to `2` (text and audio)
- [ ] `read_config_from_api` is `True` in config
- [ ] Reporting thread is started (`_init_report_threads()`)
- [ ] `report_tts_enable` is `True`
- [ ] Audio is being sent via WebSocket
- [ ] Check `ai_agent_chat_history` table for entries with `audio_id`
- [ ] Check `ai_agent_chat_audio` table for audio data

## API Endpoints Reference

### Device Management
- `POST /device/register` - Register new device
- `POST /device/bind/{agentId}/{deviceCode}` - Bind device to agent
- `GET /device/bind/{agentId}` - Get devices bound to agent

### Agent Chat History
- `GET /agent/{id}/chat-history/user` - Get user chat history
- `POST /agent/audio/{audioId}` - Get audio download UUID
- `GET /agent/play/{uuid}` - Download audio file

## Database Schema

### Device Table
```sql
CREATE TABLE ai_device (
    id VARCHAR(50) PRIMARY KEY,
    mac_address VARCHAR(50),
    agent_id VARCHAR(32),  -- Links to agent
    user_id BIGINT,
    board VARCHAR(100),
    app_version VARCHAR(50),
    create_date DATETIME,
    last_connected_at DATETIME
);
```

### Agent Table
```sql
CREATE TABLE ai_agent (
    id VARCHAR(32) PRIMARY KEY,
    agent_name VARCHAR(100),
    chat_history_conf INT,  -- 0=no, 1=text, 2=text+audio
    -- ... other fields
);
```

### Chat History Table
```sql
CREATE TABLE ai_agent_chat_history (
    id BIGINT PRIMARY KEY,
    mac_address VARCHAR(50),
    agent_id VARCHAR(32),
    session_id VARCHAR(50),
    chat_type TINYINT,  -- 1=user, 2=agent
    content VARCHAR(1024),
    audio_id VARCHAR(32),  -- Links to ai_agent_chat_audio
    created_at DATETIME
);
```

### Audio Table
```sql
CREATE TABLE ai_agent_chat_audio (
    id VARCHAR(32) PRIMARY KEY,
    audio LONGBLOB  -- Opus format audio data
);
```

