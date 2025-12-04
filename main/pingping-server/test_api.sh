#!/bin/bash

# Test script to verify Java API returns agent info
# Usage: ./test_api.sh [API_URL] [API_SECRET] [MAC_ADDRESS]

API_URL="${1:-http://localhost:8002/pingping}"
API_SECRET="${2:-your-secret-here}"
MAC_ADDRESS="${3:-A3:75:24:79:8F:1D}"

echo "Testing Java API endpoint: ${API_URL}/config/agent-models"
echo "Device MAC: ${MAC_ADDRESS}"
echo "API Secret: ${API_SECRET:0:10}..."
echo "----------------------------------------"

# Create the JSON payload
PAYLOAD=$(cat <<EOF
{
  "macAddress": "${MAC_ADDRESS}",
  "clientId": "${MAC_ADDRESS}",
  "selectedModule": {
    "VAD": null,
    "ASR": null,
    "TTS": null,
    "LLM": null,
    "Memory": null,
    "Intent": null
  }
}
EOF
)

# Make the API call
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer ${API_SECRET}" \
  -d "${PAYLOAD}" \
  "${API_URL}/config/agent-models")

# Extract HTTP code and body
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo "HTTP Status Code: ${HTTP_CODE}"
echo "----------------------------------------"
echo "Response:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
echo "----------------------------------------"

# Check if agent info is present
if echo "$BODY" | grep -q '"agent"'; then
    echo ""
    echo "✅ SUCCESS: Agent info found in response!"
    AGENT_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('agent', {}).get('id', 'NOT FOUND'))" 2>/dev/null)
    AGENT_NAME=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('data', {}).get('agent', {}).get('name', 'NOT FOUND'))" 2>/dev/null)
    echo "   Agent ID: ${AGENT_ID}"
    echo "   Agent Name: ${AGENT_NAME}"
else
    echo ""
    echo "❌ PROBLEM: No 'agent' field in response"
    if echo "$BODY" | grep -q '"code"'; then
        ERROR_MSG=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('msg', 'Unknown error'))" 2>/dev/null)
        ERROR_CODE=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('code', 'Unknown'))" 2>/dev/null)
        echo "   Error Code: ${ERROR_CODE}"
        echo "   Error Message: ${ERROR_MSG}"
    fi
fi

