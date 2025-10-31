# 🚀 Quick Start Guide

Get the SLT Chatbot up and running in minutes!

## Prerequisites Check

```bash
# Check Python version (need 3.12+)
python3 --version

# Check Node.js version (need 18+)
node --version

# Check npm version
npm --version

# Check PostgreSQL
psql --version
```

## 5-Minute Setup

### 1. Clone and Setup

```bash
# Clone repository
git clone https://github.com/KesharaGunathilaka/SLT_AI_Chatbot
cd SLT_AI_Chatbot

# Setup backend
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup frontend
cd ../frontend
npm install
```

### 2. Configure Environment

```bash
cd ../backend
cp .env.example .env
# Edit .env with your credentials:
# - DATABASE_URL (PostgreSQL connection string)
# - ZILLIZ_CLOUD_URI and ZILLIZ_CLOUD_API_KEY (from Zilliz Cloud)
# - GROQ_API_KEY (optional, from Groq console)
```

### 3. Initialize Database

```bash
# Still in backend directory with venv activated
python db_init.py
```

### 4. Crawl and Vectorize (First Time Only)

```bash
# Crawl SLT website (takes 5-10 minutes)
python crawl.py

# Vectorize content (takes 10-15 minutes)
python vectorize.py
```

### 5. Start Services

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### 6. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000

## Quick Test

Open your browser to http://localhost:5173 and try:
- "What are the broadband packages?"
- "How do I contact customer support?"

## Using Local LLM (Optional)

### With Ollama

```bash
# Install Ollama from https://ollama.ai
ollama pull llama3.1

# Update backend/llm_model.py:
# DEFAULT_CONFIG = {
#     "provider": "ollama",
#     "ollama_model": "llama3.1",
#     ...
# }
```

### With LM Studio

```bash
# 1. Download and install LM Studio from https://lmstudio.ai
# 2. Load a model (e.g., Mistral 7B)
# 3. Start local server on port 1234
# 4. Update backend/llm_model.py:
# DEFAULT_CONFIG = {
#     "provider": "lmstudio",
#     ...
# }
```

## Troubleshooting Quick Fixes

### Frontend won't connect
```bash
# Verify backend is running
curl http://localhost:8000/
```

### Database errors
```bash
# Reinitialize database
cd backend
source venv/bin/activate
python db_init.py
```

### Vector search not working
```bash
# Check Zilliz connection
python -c "from pymilvus import connections; connections.connect(uri='YOUR_URI', token='YOUR_TOKEN'); print('Connected!')"

# Re-run vectorization
python vectorize.py
```

## Development Mode

For development with hot reload:

```bash
# Backend (auto-reload on code changes)
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Frontend (auto-refresh on code changes)
npm run dev
```

## Production Build

```bash
# Frontend production build
cd frontend
npm run build
npm run preview  # Test production build

# Backend production
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Customize the chatbot responses in `backend/app.py`
- Modify the UI in `frontend/src/App.jsx`
- Add more data sources in `backend/crawl.py`

## Getting Help

- Check [Troubleshooting](README.md#-troubleshooting) section in README
- Open an issue on GitHub
- Review logs in backend for errors

---

**Happy Chatting! 🎉**
