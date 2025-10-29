# 🤖 SLT Chatbot with Local LLM

A sophisticated AI-powered chatbot for Sri Lanka Telecom (SLT) that provides intelligent customer support using Retrieval-Augmented Generation (RAG) and local/cloud LLM integration. The system scrapes and indexes SLT website content, stores it in a vector database, and uses advanced semantic search with reranking to provide accurate, context-aware responses.

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## ✨ Features

### 🎯 Core Capabilities
- **Intelligent Q&A**: Answers questions about SLT services, packages, and technical support
- **Branch Locator**: Finds nearest SLT branches based on user location
- **Multi-Source Data**: Scrapes and indexes content from SLT website with OCR support
- **Vector Search**: Semantic search with BGE-M3 embeddings (1024 dimensions)
- **Smart Reranking**: Uses cross-encoder models for improved result relevance
- **Context-Aware**: Maintains conversation context for follow-up questions
- **Real-time Updates**: Dynamic content fetching and indexing

### 🛠️ Technical Features
- **Multiple LLM Providers**: Supports Ollama (local), LM Studio, and Groq (cloud)
- **Automatic Fallback**: Falls back to cloud LLM if local models fail
- **Backup Model Support**: Automatic fallback to backup model on rate limits with retry logic
- **Rate Limit Handling**: Intelligent retry mechanism with exponential backoff for API rate limits
- **Vector Database**: Zilliz Cloud (Milvus) for scalable vector storage
- **PostgreSQL Integration**: Stores page metadata and version history
- **Async Architecture**: High-performance async web crawling with crawl4ai
- **Modern UI**: React + Vite frontend with Tailwind CSS

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│                  (React + Vite + Tailwind)                   │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP/REST
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      Backend API                             │
│                  (FastAPI + Uvicorn)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  • Query Processing                                  │   │
│  │  • Context Assembly                                  │   │
│  │  • LLM Integration (Ollama/Groq/LM Studio)          │   │
│  └──────────────────────────────────────────────────────┘   │
└──────┬─────────────────────────────────┬───────────────────┘
       │                                  │
       ▼                                  ▼
┌──────────────────┐            ┌─────────────────────┐
│  Vector Database │            │    PostgreSQL       │
│  (Zilliz/Milvus) │            │  (Page Metadata)    │
│                  │            │                     │
│  • BGE-M3        │            │  • URLs             │
│  • Embeddings    │            │  • Categories       │
│  • Similarity    │            │  • Versions         │
│    Search        │            │  • Timestamps       │
└──────────────────┘            └─────────────────────┘
       ▲                                  ▲
       │                                  │
       └──────────┬───────────────────────┘
                  │
┌─────────────────────────────────────────────────────────────┐
│                  Data Pipeline                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. Crawler (crawl4ai)                               │   │
│  │     • Async web scraping                             │   │
│  │     • Markdown generation                            │   │
│  │     • Page classification                            │   │
│  │                                                       │   │
│  │  2. Vectorizer                                       │   │
│  │     • Text chunking (LangChain)                      │   │
│  │     • BGE-M3 embeddings                              │   │
│  │     • Batch processing                               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Crawling**: Async web crawler fetches pages from slt.lk
2. **Processing**: Content converted to markdown, classified by category
3. **Storage**: Pages stored in PostgreSQL with metadata
4. **Vectorization**: Content chunked and embedded using BGE-M3
5. **Indexing**: Vectors stored in Zilliz Cloud for similarity search
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
  - Sentence Transformers
  - FlagEmbedding (BGE-M3)
- **Vector DB**: Zilliz Cloud / Milvus (pymilvus 2.5.3)
- **Database**: PostgreSQL (asyncpg)
- **Web Scraping**: 
  - crawl4ai (async crawler)
  - BeautifulSoup4
  - aiohttp
- **Text Processing**: LangChain (text splitters)
- **Geolocation**: geopy

### Frontend
- **Framework**: React 19.1.0
- **Build Tool**: Vite 7.0.0
- **Styling**: Tailwind CSS 4.1.11
- **Icons**: Lucide React
- **Markdown**: react-markdown with remark-gfm

### DevOps
- **Language**: Python 3.x, JavaScript (ES2020+)
- **Package Managers**: pip, npm
- **Linting**: ESLint

## 📦 Prerequisites

Before you begin, ensure you have the following installed:

### Required Software
- **Python**: 3.9 or higher
- **Node.js**: 18.x or higher
- **npm**: 9.x or higher
- **PostgreSQL**: 14.x or higher
- **Git**: Latest version

### External Services
- **Zilliz Cloud Account**: For vector database (or local Milvus installation)
- **Groq API Key** (optional): For cloud LLM fallback
- **Groq Backup API Key** (optional but recommended): For automatic fallback during rate limits
- **Ollama** (optional): For local LLM inference

### System Dependencies
```bash
# For Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv postgresql-client

# For macOS (using Homebrew)
brew install python postgresql
```

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/KesharaGunathilaka/SLT_Chatbot_Local_LLM.git
cd SLT_Chatbot_Local_LLM
```

### 2. Backend Setup

#### Create Virtual Environment
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Install Tesseract (for OCR - optional)
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

### 3. Frontend Setup

```bash
cd ../frontend
npm install
```

## ⚙️ Configuration

### Backend Environment Variables

Create a `.env` file in the `backend/` directory:

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/slt_chatbot

# Zilliz Cloud / Milvus Configuration
ZILLIZ_CLOUD_URI=https://your-cluster.zillizcloud.com
ZILLIZ_CLOUD_API_KEY=your_api_key_here
VECTOR_COLLECTION=slt_content

# Embedding Model Configuration
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024
EMBED_QUERY_PREFIX=

# Retrieval Configuration
SEARCH_TOP_K=20
CONTEXT_CHUNKS=4
SCORE_THRESHOLD_IP=0.2
PRIORITY_BONUS=0.001
RECENCY_BONUS_HALF_LIFE_DAYS=90
ENABLE_RERANK=true
RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# LLM Provider Configuration (optional)
GROQ_API_KEY=your_groq_api_key_here
GROQ_API_KEY_BACKUP=your_backup_groq_api_key_here

# Application Settings
EMBED_BATCH=32
```

### Database Initialization

```bash
cd backend
source venv/bin/activate
python db_init.py
```

This will:
- Create the PostgreSQL database if it doesn't exist
- Create required tables (pages, page_versions, etc.)

### Zilliz Cloud Setup

1. Sign up at [Zilliz Cloud](https://cloud.zilliz.com/)
2. Create a new cluster
3. Copy the URI and API key to your `.env` file
4. The vector collection will be created automatically during vectorization

## 📖 Usage

### Step 1: Crawl SLT Website

The crawler fetches and processes content from the SLT website:

```bash
cd backend
source venv/bin/activate
python crawl.py
```

This will:
- Crawl pages starting from the SLT sitemap
- Extract and clean content
- Classify pages by category (broadband, mobile, support, etc.)
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
- Generate embeddings using BGE-M3
- Store vectors in Zilliz Cloud
- Mark pages as vectorized

**Process**: 
- Processes pages in batches (configurable via `EMBED_BATCH`)
- Can be run multiple times to process new pages
- Progress shown via tqdm

### Step 3: Start Backend API

```bash
# Make sure you're in the backend directory with venv activated
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: `http://localhost:8000`

**Health Check**: Visit `http://localhost:8000/` to verify the API is running

### Step 4: Start Frontend

In a new terminal:

```bash
cd frontend
npm run dev
```

The frontend will be available at: `http://localhost:5173`

**Note**: The frontend is configured to connect to the backend on port 8000.

### Alternative: Simple Scraper (Legacy)

For simple scraping without vectorization:

```bash
cd backend
python scraper.py
```

This creates a basic `data/index.json` file with scraped content.

## 🔧 Running with Different LLM Providers

### Option 1: Ollama (Local)

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull a model:
   ```bash
   ollama pull mistral
   ollama pull llama3.1
   ```
3. Update `llm_model.py` default config:
   ```python
   DEFAULT_CONFIG = {
       "provider": "ollama",
       "ollama_model": "mistral",
       ...
   }
   ```

### Option 2: LM Studio (Local)

1. Install [LM Studio](https://lmstudio.ai/)
2. Load a model and start the server (port 1234)
3. Update `llm_model.py`:
   ```python
   DEFAULT_CONFIG = {
       "provider": "lmstudio",
       "lmstudio_model": "openai/gpt-oss-20b",
       ...
   }
   ```

### Option 3: Groq (Cloud)

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
   - `qwen/qwen3-32b`

**Backup Model Fallback**: The system automatically falls back to a backup model if the primary Groq API encounters rate limits (HTTP 429). The backup model:
- Uses a separate API key (`GROQ_API_KEY_BACKUP`) with its own rate limit quota
- Can use the same model (since rate limits are per API key) or a different model
- Implements exponential backoff retry logic
- Automatically retries up to `max_retries` times
- Helps ensure continuous service availability during high traffic

**Note**: Using the same model with a different API key is the default configuration, as rate limits apply per API key, not per model. This allows you to have separate rate limit quotas.

## 📚 API Documentation

### Main Endpoints

#### Health Check
```http
GET /
```

**Response:**
```json
{
  "status": "ok",
  "message": "SLT Chatbot API is running",
  "timestamp": "2025-10-12T18:23:11.855Z"
}
```

#### Chat
```http
POST /chat
Content-Type: application/json

{
  "message": "What are the broadband packages?"
}
```

**Response:**
```json
{
  "reply": "Here are the SLT broadband packages:\n\n📦 **Fiber Packages:**\n- Entry: 20 Mbps - Rs. 1,690/month\n- Family: 40 Mbps - Rs. 2,490/month\n- Premium: 100 Mbps - Rs. 4,990/month\n\n[More details](https://www.slt.lk/en/broadband/packages)"
}
```

### Query Parameters

The chat endpoint uses semantic search with the following flow:
1. Embed query using BGE-M3
2. Search vector database (top-k=20)
3. Rerank results using cross-encoder
4. Select top 4 chunks
5. Generate response using LLM

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

#### 3. Zilliz Connection Error
- Verify URI and API key in `.env`
- Check network connectivity
- Ensure cluster is active in Zilliz dashboard

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
- Ensure backend is running on port 8000
- Check CORS settings in `app.py`
- Verify frontend is configured for correct backend URL

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
      "wait_time": 3,    # Add delay before requests
  }
  ```
- **Option 3**: Switch to a local LLM provider (Ollama or LM Studio)

**How Backup Fallback Works**:
1. Primary Groq API call fails with 429 (rate limit)
2. System automatically switches to backup model using `GROQ_API_KEY_BACKUP`
3. Backup model retries with exponential backoff (5s, 10s, 20s, etc.)
4. If backup also fails after max retries, error is raised

### Debug Mode

Enable debug logging:

```python
# In app.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check System Status

```bash
# Check if backend is running
curl http://localhost:8000/

# Check if frontend is running
curl http://localhost:5173/

# Check vector collection
python -c "from pymilvus import connections, Collection; connections.connect(uri='...', token='...'); print(Collection('slt_content').num_entities)"
```

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Test thoroughly
5. Commit: `git commit -m 'Add amazing feature'`
6. Push: `git push origin feature/amazing-feature`
7. Open a Pull Request

### Code Style

- **Python**: Follow PEP 8
- **JavaScript**: Follow ESLint configuration
- **Commits**: Use conventional commits format

### Testing

```bash
# Backend
cd backend
python -m pytest

# Frontend
cd frontend
npm run test
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

- **Keshara Gunathilaka** - Initial work

## 🙏 Acknowledgments

- Sri Lanka Telecom for public content
- Ollama team for local LLM infrastructure
- Zilliz for vector database
- FastAPI and React communities

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Email: [Your email]
- Documentation: [Wiki/Docs link]

---

**Note**: This chatbot is designed for demonstration and educational purposes. Always verify critical information with official SLT sources.
