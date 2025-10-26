# 📡 API Documentation

Complete API reference for the SLT Chatbot backend.

## Base URL

```
http://localhost:8000
```

For production, replace with your deployed URL.

## Authentication

Currently, the API does not require authentication. For production deployment, consider adding:
- API key authentication
- OAuth 2.0
- JWT tokens

## Endpoints

### 1. Health Check

Check if the API is running and get system status.

**Endpoint:** `GET /`

**Request:**
```bash
curl http://localhost:8000/
```

**Response:** `200 OK`
```json
{
  "status": "ok",
  "message": "SLT Chatbot API is running",
  "timestamp": "2025-10-12T18:23:11.855Z",
  "version": "1.0.0"
}
```

---

### 2. Chat

Send a message to the chatbot and receive an AI-generated response.

**Endpoint:** `POST /chat`

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "string"
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | Yes | User's question or message |

**Example Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the broadband packages?"}'
```

**Response:** `200 OK`
```json
{
  "reply": "Here are the SLT broadband packages:\n\n📦 **Fiber Packages:**\n- Entry: 20 Mbps - Rs. 1,690/month\n- Family: 40 Mbps - Rs. 2,490/month\n- Premium: 100 Mbps - Rs. 4,990/month\n\n[More details](https://www.slt.lk/en/broadband/packages)",
  "sources": [
    {
      "url": "https://www.slt.lk/en/broadband/packages",
      "relevance_score": 0.89
    }
  ]
}
```

**Error Responses:**

`400 Bad Request` - Empty or invalid message
```json
{
  "error": "Message is required",
  "message": "The 'message' field cannot be empty"
}
```

`500 Internal Server Error` - Server error
```json
{
  "error": "Internal server error",
  "message": "Failed to process request"
}
```

---

## Request/Response Flow

### Chat Request Processing

1. **Input Validation**: Check if message is non-empty
2. **Query Embedding**: Convert message to vector using BGE-M3
3. **Vector Search**: Search Zilliz database for similar content
4. **Filtering**: Apply relevance threshold (score > 0.2)
5. **Reranking**: Use cross-encoder to rerank top-k results
6. **Context Assembly**: Combine top chunks into context
7. **LLM Generation**: Generate response using selected LLM
8. **Response Formatting**: Format and return response

### Vector Search Parameters

The chat endpoint uses these configurable parameters (set in .env):

```env
SEARCH_TOP_K=20              # Retrieve 20 candidates
CONTEXT_CHUNKS=4             # Use top 4 for LLM
SCORE_THRESHOLD_IP=0.2       # Minimum similarity
ENABLE_RERANK=true           # Use cross-encoder
```

---

## Response Formats

### Success Response

```json
{
  "reply": "string",           // AI-generated response
  "sources": [                 // Optional: source pages
    {
      "url": "string",
      "relevance_score": 0.89
    }
  ]
}
```

### Error Response

```json
{
  "error": "string",           // Error type
  "message": "string",         // Human-readable message
  "details": {}                // Optional: additional info
}
```

---

## Usage Examples

### JavaScript (Fetch API)

```javascript
async function askChatbot(message) {
  try {
    const response = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    });
    
    const data = await response.json();
    return data.reply;
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
}

// Usage
const answer = await askChatbot('What are the broadband packages?');
console.log(answer);
```

### Python (Requests)

```python
import requests

def ask_chatbot(message: str) -> str:
    url = "http://localhost:8000/chat"
    payload = {"message": message}
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    
    return response.json()["reply"]

# Usage
answer = ask_chatbot("What are the broadband packages?")
print(answer)
```

### cURL

```bash
# Simple query
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the broadband packages?"}'

# Pretty print response
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find SLT branches in Colombo"}' \
  | jq '.'
```

---

## Rate Limiting

Currently, no rate limiting is implemented. For production:

```python
# Recommended rate limiting
# Install: pip install slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/chat")
@limiter.limit("10/minute")  # 10 requests per minute
async def chat(request: Request, data: ChatRequest):
    # ... existing code
```

---

## CORS Configuration

CORS is currently configured to allow all origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, restrict to specific domains:

```python
allow_origins=[
    "https://yourdomain.com",
    "https://www.yourdomain.com"
]
```

---

## Query Capabilities

The chatbot can handle:

### 1. General Questions
```json
{"message": "What services does SLT offer?"}
{"message": "How do I apply for a new connection?"}
```

### 2. Package Information
```json
{"message": "Tell me about broadband packages"}
{"message": "What's the speed of the premium plan?"}
{"message": "Compare fiber and ADSL packages"}
```

### 3. Branch Location
```json
{"message": "Find SLT branches near me"}
{"message": "Where is the nearest SLT office?"}
{"message": "SLT branches in Colombo"}
```

### 4. Technical Support
```json
{"message": "How to reset my router?"}
{"message": "My internet is slow, what should I do?"}
{"message": "How to check my data usage?"}
```

### 5. Billing & Payments
```json
{"message": "How do I pay my bill online?"}
{"message": "What are the payment methods?"}
{"message": "Can I pay using mobile app?"}
```

---

## Response Time

Typical response times:
- **With Groq (cloud)**: 1-3 seconds
- **With Ollama (local)**: 3-10 seconds
- **With LM Studio (local)**: 2-8 seconds

Factors affecting response time:
- LLM provider and model size
- Number of retrieved chunks
- Reranking enabled/disabled
- Network latency (for cloud LLMs)

---

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 400 | Bad Request | Check request format and required fields |
| 404 | Not Found | Verify endpoint URL |
| 500 | Internal Server Error | Check server logs, database connection |
| 503 | Service Unavailable | LLM service down, check Ollama/Groq |

---

## WebSocket Support (Future)

For real-time streaming responses:

```javascript
// Planned feature
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onmessage = (event) => {
  const chunk = JSON.parse(event.data);
  console.log(chunk.text);  // Stream tokens as they arrive
};

ws.send(JSON.stringify({ message: "Tell me about SLT" }));
```

---

## Testing

### Test Health Endpoint
```bash
curl http://localhost:8000/
```

### Test Chat Endpoint
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'
```

### Load Testing
```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Run load test
ab -n 100 -c 10 -p request.json -T application/json \
  http://localhost:8000/chat
```

---

## Monitoring

Recommended monitoring for production:

```python
# Add request logging
import logging
from datetime import datetime

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = (datetime.now() - start_time).total_seconds()
    
    logging.info(f"{request.method} {request.url} - {response.status_code} - {duration}s")
    return response
```

---

## API Versioning (Future)

Planned API versioning:

```
/v1/chat
/v2/chat
```

Current version is v1 (implicit).

---

## Best Practices

1. **Always validate responses**: Check for error fields
2. **Handle timeouts**: Set reasonable timeout values (30s+)
3. **Cache responses**: Cache common queries client-side
4. **Retry logic**: Implement exponential backoff for failures
5. **Error handling**: Always catch and handle errors gracefully

---

## Support

For API issues:
- Check server logs: `tail -f backend/logs/*.log`
- Verify configuration: `.env` file
- Test with curl before using in code
- Open issue on GitHub with request/response details
