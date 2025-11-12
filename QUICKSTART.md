# 🚀 Quick Start Guide

Get the SLT Chatbot up and running in minutes!

## Prerequisites Check

```powershell
# Check Python (3.12+ recommended)
python --version

# Check Node.js (18+)
node --version
npm --version

# Check Docker Desktop (must be running)
docker --version

# Check PostgreSQL client
psql --version
```

## 5-Minute Setup

### 1. Clone and Setup

```powershell
# Clone repository
git clone https://github.com/KesharaGunathilaka/SLT_AI_Chatbot
cd SLT_AI_Chatbot

# Backend setup
cd backend
python -m venv .venv
./venv/Scripts/Activate
pip install --upgrade pip
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
```

### 2. Start Milvus (Docker, Standalone)

Milvus must listen on localhost:19530 (the backend is pre-configured for this).

Option A — If this repository contains a helper script (milvus/standalone.bat):
```powershell
./milvus/standalone.bat start
```

Option B — Single Docker container (persistent volume):
```powershell
# Pull latest stable Milvus image (2.4+)
docker pull milvusdb/milvus:latest

# Start standalone Milvus with embedded dependencies
docker run -d --name milvus-standalone `
	-p 19530:19530 -p 9091:9091 `
	-v milvus_data:/var/lib/milvus `
	-e ETCD_USE_EMBED=true -e MINIO_USE_EMBED=true `
	milvusdb/milvus:latest

# Verify it's up
docker ps --filter "name=milvus-standalone"
```

Health check from Python:
```powershell
python -c "from pymilvus import connections; connections.connect(host='localhost', port='19530'); print('Milvus OK')"
```

### 3. Configure environment

Create a `.env` file inside `backend`:

```powershell
@"
# PostgreSQL (adjust to your local DB)
DATABASE_URL=postgresql://user:password@localhost:5432/slt_chatbot

# Vector DB
VECTOR_COLLECTION=SLT_AI

# Embeddings
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
EMBEDDING_DIM=768

# Retrieval and ranking
SEARCH_TOP_K=30
CONTEXT_CHUNKS=5
SCORE_THRESHOLD_IP=0.25
ENABLE_RERANK=true
RERANK_MODEL=BAAI/bge-reranker-base
RERANK_TOP_K=20
"@
```

Notes:
- Milvus host/port are hard-coded to `localhost:19530` in the backend. If you change ports, update `backend/app.py` and `backend/vectorize.py` accordingly.
- PostgreSQL stores page metadata; Milvus stores vectors.

### 4. Initialize PostgreSQL

```powershell
cd ../backend
./venv/Scripts/Activate
python db_init.py
```

### 5. Crawl and vectorize (First Run)

```powershell
# Crawl SLT website
python crawl.py

# Create embeddings and push to Milvus
python vectorize.py
```

### 6. Start services

Terminal 1 — Backend API:
```powershell
cd backend
./venv/Scripts/Activate
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 — Frontend:
```powershell
cd frontend
npm run dev
```

### 7. Access the Application

- Frontend: http://localhost:5173
- Backend:  http://localhost:8000

## Quick Test

Open your browser to http://localhost:5173 and try:
- "What are the broadband packages?"
- "How do I contact customer support?"

## Using Local LLM (Optional)

### Ollama
```powershell
# Install from https://ollama.ai
ollama pull llama3.1 #prefered model

# Update backend/llm_model.py:
# DEFAULT_CONFIG = {
#     "provider": "ollama",
#     "ollama_model": "llama3.1",
#     ...
# }
```

## Troubleshooting Quick Fixes

- Frontend can’t connect
```powershell
curl http://localhost:8000/
```

- PostgreSQL issues
```powershell
python db_init.py  # re-create tables
```

- Milvus/vector search not working
```powershell
# Check container
docker logs --tail 100 milvus-standalone

# Test connection
python -c "from pymilvus import connections; connections.connect(host='localhost', port='19530'); print('Milvus OK')"

# Re-run vectorization
python vectorize.py
```

## Development Mode

For development with hot reload:

```powershell
# Backend (auto-reload on code changes)
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Frontend (auto-refresh on code changes)
npm run dev
```

## Production Build

```powershell
# Frontend
cd frontend
npm run build
npm run preview

# Backend (increase workers as needed)
cd ../backend
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Need more?

- Read the full [README.md](README.md) for detailed documentation
- Customize the chatbot responses in `backend/app.py`
- Modify the UI in `frontend/src/App.jsx`
- Add more data sources in `backend/crawl.py`

## Getting Help

- Check [Troubleshooting](README.md#-troubleshooting) section in README
- Open an issue on GitHub
- Review logs in backend for errors

---

— Happy Chatting! 🎉
