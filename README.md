# 🤖 SLT AI Chatbot

AI-powered chatbot for Sri Lanka Telecom (SLT) that provides intelligent customer support using Retrieval-Augmented Generation (RAG) and local/cloud LLM integration. The system scrapes and indexes SLT website content, stores it in Milvus (vector database), and uses hybrid search with optional reranking to provide accurate, context-aware responses.

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Overview](#-api-overview)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## ✨ Features

### 🎯 Core Capabilities
- **Intelligent Q&A**: Answers questions about SLT services, packages, and support
- **Multi-Source Data**: Scrapes and indexes content from the SLT website
- **Hybrid Search**: Dense vector search (Milvus) + BM25 keyword search
- **Embeddings**: Default `BAAI/bge-base-en-v1.5` (768-dim), configurable
- **Smart Reranking (optional)**: `BAAI/bge-reranker-base` via FlagEmbedding or CrossEncoder
- **Multi-Query Expansion (optional)**: Expands queries to improve recall
- **Context-Aware**: Maintains conversation context for follow-up questions
- **Real-time Updates**: Crawl and re-vectorize content as needed

### 🛠️ Technical Features
- **Multiple LLM Providers**: Supports Ollama (local), LM Studio, and Groq (cloud)
- **Automatic Fallback**: Falls back to cloud LLM if given LLM models fail
- **Backup Model Support**: Automatic fallback to backup model on rate limits with retry logic
- **Rate Limit Handling**: Intelligent retry mechanism with exponential backoff for API rate limits
- **Vector Database**: Milvus (runs locally in Docker) for scalable vector storage
- **PostgreSQL Integration**: Stores page metadata and version history
- **Async Architecture**: High-performance async web crawling with crawl4ai
- **Modern UI**: React + Vite frontend with Tailwind CSS

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                            │
│                  (React + Vite + Tailwind)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP/REST
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      Backend API                            │
│                  (FastAPI + Uvicorn)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • Query Processing                                  │   │
│  │  • Context Assembly                                  │   │
│  │  • LLM Integration (Ollama/Groq/LM Studio)           │   │
│  └──────────────────────────────────────────────────────┘   │
└──────┬──────────────────────────────────┬───────────────────┘
       │                                  │
       ▼                                  ▼
┌──────────────────┐            ┌─────────────────────┐
│  Vector Database │            │    PostgreSQL       │
│     (Milvus)     │            │   (Page Metadata)   │
│                  │            │                     │
│  • BGE-base      │            │  • URLs             │
│  • Embeddings    │            │  • Categories       │
│  • Similarity    │            │  • Versions         │
│    Search        │            │  • Timestamps       │
└──────────────────┘            └─────────────────────┘
       ▲                                  ▲
       │                                  │
       └──────────┬───────────────────────┘
                  │
┌─────────────────────────────────────────────────────────────┐
│                  Data Pipeline                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. Crawler (crawl4ai)                               │   │
│  │     • Async web scraping                             │   │
│  │     • Markdown generation                            │   │
│  │     • Page classification                            │   │
│  │                                                      │   │
│  │  2. Vectorizer                                       │   │
│  │     • Text chunking (LangChain)                      │   │
│  │     • BGE-base embeddings                            │   │
│  │     • Batch processing                               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Crawling**: Async web crawler fetches pages from slt.lk
2. **Processing**: Content converted to markdown, classified and cleaned using LLM
3. **Storage**: Pages stored in PostgreSQL with metadata
4. **Vectorization**: Content chunked and embedded using BGE-base (Sentence Transformers)
5. **Indexing**: Vectors stored in Milvus for similarity search
6. **Query**: User questions embedded and matched against vector index
7. **Retrieval**: Top-k results retrieved and reranked
8. **Generation**: LLM generates response using retrieved context

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI 0.115.0
- **Server**: Uvicorn (with uvloop for performance)
- **LLM Integration**:
  - Ollama (local models)
  - LM Studio (local OpenAI-compatible)
  - Groq API (cloud with backup fallback support)
- **Embeddings**:
  - Sentence Transformers (default: `BAAI/bge-base-en-v1.5`, 768-dim)
- **Reranking**:
  - Optional reranker: `BAAI/bge-reranker-base` (FlagEmbedding or CrossEncoder)
- **Vector DB**: Milvus (pymilvus)
- **Database**: PostgreSQL (asyncpg)
- **Web Scraping**:
  - crawl4ai (async crawler)
  - BeautifulSoup4
- **Text Processing**: LangChain (text splitters)

### Frontend
- **Framework**: React 19.1.0
- **Build Tool**: Vite 7.0.0
- **Styling**: Tailwind CSS 4.1.11
- **Icons**: Lucide React
- **Markdown**: react-markdown with remark-gfm

## 📦 Prerequisites

Before you begin, ensure you have the following installed:

### Required Software
- **Python**: 3.12 or higher (3.10+ also works)
- **Node.js**: 18.x or higher
- **npm**: 9.x or higher
- **PostgreSQL**: 14.x or higher
- **Docker Desktop**: Latest (for running Milvus locally)
- **Git**: Latest version

### External Services
- **Postgres** runs locally.
- **Milvus** runs locally in Docker.
- **Ollama**: For local LLM inference
- **Groq API Key** (optional): For cloud LLM
- **Groq Backup API Key** (optional but recommended): For automatic fallback during rate limits

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/KesharaGunathilaka/SLT_AI_Chatbot
cd SLT_AI_Chatbot
```

### 2. Backend Setup

#### Create Virtual Environment
```powershell
cd backend
python -m venv .venv  # Recommend Python 3.12+
./.venv/Scripts/activate
```

#### Install Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Frontend Setup

```powershell
cd ../frontend
npm install
```

## ⚙️ Configuration

### Backend Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Database Configuration (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/slt_chatbot

# Milvus Configuration
# Host/port are hard-coded to localhost:19530 in code. Change code if ports differ.
VECTOR_COLLECTION=SLT_AI

# Embedding Model Configuration
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
EMBEDDING_DIM=768

# Embedding batch size (vectorization)
EMBED_BATCH=32

# Retrieval / Scoring Configuration
SEARCH_TOP_K=30
CONTEXT_CHUNKS=5
SCORE_THRESHOLD_IP=0.25
PRIORITY_BONUS=0.001
RECENCY_BONUS=0.03
RECENCY_BONUS_HALF_LIFE_DAYS=60

# Reranking
ENABLE_RERANK=true
RERANK_MODEL=BAAI/bge-reranker-base
RERANK_TOP_K=20

# Multi-Query Expansion (optional)
ENABLE_MQE=true
MQE_QUERIES=2

# LLM Provider Configuration (optional)
GROQ_API_KEY=your_groq_api_key_here
GROQ_API_KEY_BACKUP=your_backup_groq_api_key_here

```

### Frontend Environment Variables

Create `frontend/.env.local` with the backend API URL you use during development:

```bash
# If you start backend on port 8000 (recommended via uvicorn)
VITE_FRONTEND_API_URL=http://localhost:8000
```

### Database Initialization

```powershell
cd backend
./.venv/Scripts/activate
python db_init.py
```

This will:
- Create the PostgreSQL database if it doesn't exist
- Create required tables (pages, page_versions, etc.)

### Milvus Setup (Docker, Windows)

Run Milvus locally in Docker (listening on 19530 and 9091):

```powershell
docker pull milvusdb/milvus:latest
docker run -d --name milvus-standalone `
  -p 19530:19530 -p 9091:9091 `
  -v milvus_data:/var/lib/milvus `
  -e ETCD_USE_EMBED=true -e MINIO_USE_EMBED=true `
  milvusdb/milvus:latest

# Health check
python -c "from pymilvus import connections; connections.connect(host='localhost', port='19530'); print('Milvus OK')"
```

The vector collection (`VECTOR_COLLECTION`) will be created automatically by `vectorize.py` if it doesn't exist.

## 📖 Usage

### Run Local LLM
```bash
ollama run llama3.1  # or mistral (imported model)
```

### Step 1: Crawl SLT Website

The crawler fetches and processes content from the SLT website:

```powershell
cd backend
./.venv/Scripts/activate
python crawl.py
```

This will:
- Crawl pages starting from the SLT sitemap
- Extract and clean content
- Classify pages by category
- Store pages in PostgreSQL
- Save raw markdown files to `./data/crawl/`

**Configuration**: Edit `crawl.py` to modify:
- `SITEMAP_URL`: Starting point for crawling
- `BASE_URL`: Base domain
- `LLM_CONCURRENCY`: Parallel classification tasks

### Step 2: Vectorize Content

Convert crawled content into vector embeddings:

```bash
python vectorize.py
```

This will:
- Load pages from PostgreSQL
- Split content into chunks (1000 chars, 200 overlap)
- Generate embeddings using BGE
- Store vectors in Milvus
- Mark pages as vectorized

**Process**: 
- Processes pages in batches (configurable via `EMBED_BATCH`)
- Can be run multiple times to process new pages
- Progress shown via tqdm

### Step 3: Start Backend API

Option A — Recommended (uvicorn on port 8000):

```powershell
# Make sure you're in the backend directory with venv activated
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Option B — Run the module directly (defaults to port 8000):

```powershell
python app.py
```

Set `VITE_FRONTEND_API_URL` to match the port you choose (see Frontend env vars above).

### Step 4: Start Frontend

In a new terminal:

```powershell
cd frontend
npm run dev
```

The frontend will be available at: `http://localhost:5173`

Note: The frontend uses `VITE_FRONTEND_API_URL` to reach the backend. Ensure it matches your backend port.


## 🔧 Running with Different LLM Providers

### Option 1: Ollama (Local)

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull a model:
  ```powershell
   ollama pull llama3.1
   ```
3. Update `llm_model.py` default config:
   ```python
   DEFAULT_CONFIG = {
       "provider": "ollama",
       "ollama_model": "llama3.1",
       ...
   }
   ```

### Option 2: Groq (Cloud)

1. Get API key from [Groq](https://console.groq.com/)
2. Add to `.env`:
   ```bash
   GROQ_API_KEY=your_key_here
   GROQ_API_KEY_BACKUP=your_backup_key_here  # Optional: for automatic fallback
   ```
3. Update `llm_model.py`:
   ```python
   DEFAULT_CONFIG = {
       "provider": "groq",
       "groq_model": "openai/gpt-oss-120b",
       "backup_model": "openai/gpt-oss-120b",  # Model to use when rate limited
       "max_retries": 3,  # Max retries for backup model
       ...
   }
   ```
   
   **Available Groq Models**: You can use any Groq-supported model such as:
   - `openai/gpt-oss-120b` (default)
   - `llama-3.3-70b-versatile`

**Backup Model Fallback**: The system automatically falls back to a backup model if the primary Groq API encounters rate limits (HTTP 429). The backup model:
- Uses a separate API key (`GROQ_API_KEY_BACKUP`) with its own rate limit quota
- Can use the same model (since rate limits are per API key) or a different model
- Implements exponential backoff retry logic
- Automatically retries up to `max_retries` times
- Helps ensure continuous service availability during high traffic

**Note**: Using the same model with a different API key is the default configuration, as rate limits apply per API key, not per model. This allows you to have separate rate limit quotas.

## 📚 API Overview

### Main Endpoint

#### Chat
```http
POST /chat
Content-Type: application/json

{
  "message": "What are the broadband packages?"
}
```

**Response (example):**
```json
{
  "reply": "Here are the SLT broadband packages:\n\n📦 **Fiber Packages:**\n- Entry: 20 Mbps - Rs. 1,690/month\n- Family: 40 Mbps - Rs. 2,490/month\n- Premium: 100 Mbps - Rs. 4,990/month\n\n[More details](https://www.slt.lk/en/broadband/packages)"
}
```

### Retrieval flow (high level)
1. Embed query using the configured SentenceTransformer model (default bge-base)
2. Hybrid search: vector search (Milvus) + BM25 keyword search
3. Optional Multi-Query Expansion to broaden recall
4. Optional reranking using a cross-encoder/FlagEmbedding model
5. Select top chunks and generate a response with the chosen LLM

## 🐛 Troubleshooting

### Common Issues

#### 1. Import Error: No module named 'crawl4ai'
```bash
pip install crawl4ai
```

#### 2. PostgreSQL Connection Error
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check connection string in `.env`
- Ensure database exists: `python db_init.py`

#### 3. Milvus Connection Error
- Ensure Docker container is running: `docker ps | findstr milvus`
- Check logs: `docker logs --tail 200 milvus-standalone`
- Test from Python:
  ```powershell
  python -c "from pymilvus import connections; connections.connect(host='localhost', port='19530'); print('Milvus OK')"
  ```

#### 4. Ollama Not Responding
```bash
# Check if Ollama is running
ollama list

# Start Ollama service
ollama serve

# Test connection
curl http://localhost:11434/api/generate -d '{"model": "mistral", "prompt": "test"}'
```

#### 5. Frontend Can't Connect to Backend
- Ensure the backend is running (8000 if using uvicorn or if using `python app.py`)
- Check CORS settings in `backend/app.py`
- Verify `frontend/.env.local` sets `VITE_FRONTEND_API_URL` to the correct backend URL

#### 6. Embeddings Taking Too Long
- Reduce `SEARCH_TOP_K` in `.env`
- Use smaller embedding model
- Increase `EMBED_BATCH` size

#### 7. Out of Memory During Vectorization
- Reduce batch size: `EMBED_BATCH=8`
- Process fewer pages at once
- Use lighter embedding model

#### 8. Groq API Rate Limit Errors
If you encounter rate limit errors (HTTP 429):
- **Option 1**: Configure a backup API key:
  ```bash
  # In .env file
  GROQ_API_KEY_BACKUP=your_backup_key_here
  ```
- **Option 2**: Adjust retry settings in `llm_model.py`:
  ```python
  DEFAULT_CONFIG = {
      "max_retries": 5,  # Increase max retries
      "wait_time": 20,    # Add delay before requests
  }
  ```
- **Option 3**: Switch to a local LLM provider (Ollama or LM Studio)

**How Backup Fallback Works**:
1. Primary Groq API call fails with 429 (rate limit)
2. System automatically switches to backup model using `GROQ_API_KEY_BACKUP`
3. Backup model retries with exponential backoff (5s, 10s, 20s, etc.)
4. If backup also fails after max retries, error is raised

### Check System Status

```powershell
# Check if backend is running
curl http://localhost:8000/

# Check if frontend is running
curl http://localhost:5173/

# Check vector collection
python -c "from pymilvus import connections, Collection; connections.connect(host='localhost', port='19530'); print(Collection('SLT_AI').num_entities)"
```

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Test thoroughly
5. Commit: `git commit -m 'Add your feature'`
6. Push: `git push origin feature/your-feature`
7. Open a Pull Request

## 👥 Team

- **Keshara Gunathilaka**
- **Thinula Harishchandra**
- **Randil Jayasinghe**
- **Mevinu Gunarathna**

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Email: [gpkhgunathilaka@gmail.com]
- Documentation: Inside the Documents Folder

---

**Note**: This chatbot is designed for demonstration and educational purposes. Always verify critical information with official SLT sources.
