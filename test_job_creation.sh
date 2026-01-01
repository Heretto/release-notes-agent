#!/bin/bash

# Login and get token
echo "Logging in..."
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}')

TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//')

if [ -z "$TOKEN" ]; then
  echo "Failed to get token. Response:"
  echo $TOKEN_RESPONSE
  exit 1
fi

echo "Got token: ${TOKEN:0:20}..."

# Get first instruction set
echo "Getting instruction sets..."
INSTRUCTIONS=$(curl -s -X GET http://localhost:8000/api/v1/instructions/ \
  -H "Authorization: Bearer $TOKEN")

echo "Instructions response: ${INSTRUCTIONS:0:100}..."

# Extract first instruction ID
INSTRUCTION_ID=$(echo $INSTRUCTIONS | grep -o '"id":"[^"]*' | head -1 | sed 's/"id":"//')

if [ -z "$INSTRUCTION_ID" ]; then
  echo "No instruction sets found. Please create one first."
  exit 1
fi

echo "Using instruction ID: $INSTRUCTION_ID"

# Create a job
echo "Creating job..."
JOB_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"instruction_set_id\": \"$INSTRUCTION_ID\",
    \"jql_query\": \"project = TEST\",
    \"output_filename\": \"test-release-notes.xml\",
    \"publish_to_heretto\": false
  }")

echo "Job creation response:"
echo $JOB_RESPONSE | python3 -m json.tool 2>/dev/null || echo $JOB_RESPONSE