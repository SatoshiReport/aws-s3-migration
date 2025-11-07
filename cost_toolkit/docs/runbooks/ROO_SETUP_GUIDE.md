# OpenAI-Compatible Embedding Server for Roo Code Indexing

This guide shows how to set up and use the embedding server as an OpenAI-compatible endpoint for Roo code indexing.

## Quick Setup

1. **Install dependencies:**
```bash
pip3 install -r requirements_embedding.txt
```

2. **Start the server:**
```bash
python3 embedding_server.py --port 8080
```

3. **Verify it's working:**
```bash
python3 test_openai_compatibility.py
```

## OpenAI API Compatibility

The server implements the OpenAI Embeddings API specification:

### Base URL
```
http://localhost:8080
```

### Available Endpoints

#### List Models
```bash
curl http://localhost:8080/v1/models
```

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "text-embedding-ada-002",
      "object": "model",
      "created": 1677610602,
      "owned_by": "openai"
    }
  ]
}
```

#### Create Embeddings
```bash
curl -X POST http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": ["def hello():\n    print(\"Hello World\")"],
    "model": "text-embedding-ada-002"
  }'
```

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.1, 0.2, 0.3, ...]
    }
  ],
  "model": "text-embedding-ada-002",
  "usage": {
    "prompt_tokens": 8,
    "total_tokens": 8
  }
}
```

## Roo Integration Configuration

### Option 1: Environment Variables
Set these environment variables for Roo to use your local embedding server:

```bash
export OPENAI_API_BASE="http://localhost:8080/v1"
export OPENAI_API_KEY="dummy-key"  # Any value works
```

### Option 2: Configuration File
If Roo uses a configuration file, set:

```yaml
# roo-config.yaml
embeddings:
  provider: openai
  api_base: "http://localhost:8080/v1"
  api_key: "dummy-key"
  model: "text-embedding-ada-002"
```

### Option 3: Command Line Arguments
If Roo accepts command line arguments:

```bash
roo --embedding-api-base http://localhost:8080/v1 \
    --embedding-model text-embedding-ada-002 \
    --embedding-api-key dummy-key
```

## Code Examples for Integration

### Python Client Example
```python
import openai

# Configure client to use local server
openai.api_base = "http://localhost:8080/v1"
openai.api_key = "dummy-key"

# Generate embeddings
response = openai.Embedding.create(
    input=["def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)"],
    model="text-embedding-ada-002"
)

embeddings = response['data'][0]['embedding']
print(f"Embedding dimension: {len(embeddings)}")
```

### JavaScript/Node.js Example
```javascript
const { Configuration, OpenAIApi } = require("openai");

const configuration = new Configuration({
  apiKey: "dummy-key",
  basePath: "http://localhost:8080/v1"
});

const openai = new OpenAIApi(configuration);

async function getEmbeddings(code) {
  const response = await openai.createEmbedding({
    model: "text-embedding-ada-002",
    input: [code]
  });
  
  return response.data.data[0].embedding;
}
```

### cURL Example for Testing
```bash
# Test with actual code
curl -X POST http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      "class Calculator:\n    def add(self, a, b):\n        return a + b",
      "function multiply(a, b) {\n    return a * b;\n}",
      "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)"
    ],
    "model": "text-embedding-ada-002"
  }'
```

## Performance Characteristics

- **Embedding Dimension:** 384
- **Max Input Length:** 256 tokens
- **Processing Speed:** ~4-6 embeddings/second on Apple Silicon
- **Memory Usage:** ~500MB
- **Startup Time:** ~6 seconds

## Production Deployment

For production use with Roo:

### 1. Use a Production WSGI Server
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 embedding_server:app
```

### 2. Add Authentication (Optional)
Modify the server to check for API keys if needed:

```python
@app.before_request
def check_auth():
    if request.endpoint in ['create_embeddings', 'list_models']:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": {"message": "Invalid API key", "type": "authentication_error"}}), 401
```

### 3. Run as a Service
Create a systemd service file:

```ini
[Unit]
Description=Roo Embedding Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/embedding/server
ExecStart=/usr/bin/python3 embedding_server.py --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Use Docker (Alternative)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements_embedding.txt .
RUN pip install -r requirements_embedding.txt

COPY embedding_server.py .
EXPOSE 8080

CMD ["python", "embedding_server.py", "--port", "8080", "--host", "0.0.0.0"]
```

## Troubleshooting

### Common Issues

1. **Port already in use:**
   ```bash
   python3 embedding_server.py --port 8081
   ```

2. **Roo can't connect:**
   - Ensure server is running: `curl http://localhost:8080/health`
   - Check firewall settings
   - Verify API base URL in Roo configuration

3. **Performance issues:**
   - Use a smaller model for faster inference
   - Increase batch size for multiple embeddings
   - Consider using a GPU-enabled server for large workloads

### Monitoring
Check server logs for request processing:
```bash
tail -f embedding_server.log
```

### Health Check
```bash
curl http://localhost:8080/health
# Should return: {"status": "healthy", "model_loaded": true}
```

## Model Alternatives

You can use different models by starting the server with:

```bash
# Larger, more accurate model (slower)
python3 embedding_server.py --model sentence-transformers/all-mpnet-base-v2

# Smaller, faster model
python3 embedding_server.py --model sentence-transformers/all-MiniLM-L12-v2

# Code-specific model (if available)
python3 embedding_server.py --model sentence-transformers/all-distilroberta-v1
```

## Integration Verification

After setting up, verify Roo can use the embeddings:

1. **Start the embedding server**
2. **Configure Roo to use local endpoint**
3. **Run Roo's indexing command**
4. **Check server logs for embedding requests**

The server will log each embedding request, showing successful integration with Roo.