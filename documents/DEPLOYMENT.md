# 🚀 Deployment Guide

Complete guide for deploying the SLT Chatbot to production environments.

## 📋 Table of Contents

- [Deployment Options](#deployment-options)
- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Monitoring](#monitoring)
- [Security](#security)
- [Backup & Recovery](#backup--recovery)

## 🎯 Deployment Options

### Option 1: Docker (Recommended)
- **Pros**: Consistent environment, easy scaling, portable
- **Cons**: Requires Docker knowledge
- **Best for**: Most production deployments

### Option 2: Traditional Server
- **Pros**: Direct control, no containerization overhead
- **Cons**: Manual dependency management
- **Best for**: Single server deployments

### Option 3: Cloud Platforms
- **Pros**: Managed infrastructure, auto-scaling
- **Cons**: Vendor lock-in, cost
- **Best for**: High-traffic applications

## 🔧 Prerequisites

### Production Requirements
- **Server**: 4+ CPU cores, 16GB+ RAM, 100GB+ storage
- **OS**: Ubuntu 22.04 LTS or similar
- **Network**: Static IP, SSL certificate
- **Database**: PostgreSQL 14+ (managed or self-hosted)
- **Vector DB**: Zilliz Cloud account (or Milvus cluster)

### Domain & SSL
```bash
# Get free SSL certificate with Let's Encrypt
sudo apt-get install certbot
sudo certbot certonly --standalone -d yourdomain.com
```

## ⚙️ Environment Setup

### Production Environment Variables

Create `/etc/slt-chatbot/.env`:

```bash
# Production mode
NODE_ENV=production
PYTHON_ENV=production

# Database (use managed PostgreSQL for production)
DATABASE_URL=postgresql://user:password@db-host:5432/slt_chatbot

# Zilliz Cloud
ZILLIZ_CLOUD_URI=https://your-prod-cluster.zillizcloud.com
ZILLIZ_CLOUD_API_KEY=your_production_api_key
VECTOR_COLLECTION=slt_content_prod

# LLM Configuration
GROQ_API_KEY=your_production_groq_key

# Security
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Performance
WORKERS=4
EMBED_BATCH=64
SEARCH_TOP_K=20
```

### Security Hardening

```bash
# Create dedicated user
sudo useradd -m -s /bin/bash slt-chatbot
sudo usermod -aG sudo slt-chatbot

# Set file permissions
sudo chown -R slt-chatbot:slt-chatbot /opt/slt-chatbot
sudo chmod 700 /etc/slt-chatbot/.env
```

## 🐳 Docker Deployment

### 1. Create Dockerfiles

**Backend Dockerfile** (`backend/Dockerfile`):

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 chatbot && chown -R chatbot:chatbot /app
USER chatbot

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

# Run application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Frontend Dockerfile** (`frontend/Dockerfile`):

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source
COPY . .

# Build application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 2. Docker Compose

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    container_name: slt-backend
    restart: always
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./backend/data:/app/data
      - ./backend/logs:/app/logs
    depends_on:
      - postgres
    networks:
      - slt-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build: ./frontend
    container_name: slt-frontend
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
    networks:
      - slt-network

  postgres:
    image: postgres:15-alpine
    container_name: slt-postgres
    restart: always
    environment:
      POSTGRES_DB: slt_chatbot
      POSTGRES_USER: chatbot
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./backup:/backup
    networks:
      - slt-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U chatbot"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres-data:

networks:
  slt-network:
    driver: bridge
```

### 3. Nginx Configuration

**frontend/nginx.conf**:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Root directory
    root /usr/share/nginx/html;
    index index.html;

    # Frontend
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
}
```

### 4. Deploy with Docker

```bash
# Build and start services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Update services
docker-compose pull
docker-compose up -d --build
```

## ☁️ Cloud Deployment

### AWS Deployment

#### Using ECS (Elastic Container Service)

1. **Push images to ECR**:
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t slt-backend ./backend
docker tag slt-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/slt-backend:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/slt-backend:latest
```

2. **Create ECS task definition**
3. **Create ECS service**
4. **Configure load balancer**
5. **Set up RDS for PostgreSQL**

### Google Cloud Platform

#### Using Cloud Run

```bash
# Deploy backend
gcloud run deploy slt-backend \
  --image gcr.io/project-id/slt-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

# Deploy frontend
gcloud run deploy slt-frontend \
  --image gcr.io/project-id/slt-frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### Azure

#### Using Azure Container Instances

```bash
# Create resource group
az group create --name slt-chatbot --location eastus

# Deploy container
az container create \
  --resource-group slt-chatbot \
  --name slt-backend \
  --image <registry>/slt-backend:latest \
  --cpu 2 --memory 4 \
  --environment-variables DATABASE_URL=<url>
```

## 📊 Monitoring

### Application Monitoring

**Add monitoring to backend** (`app.py`):

```python
from prometheus_client import Counter, Histogram, generate_latest
import time

# Metrics
REQUEST_COUNT = Counter('request_count', 'App Request Count', ['method', 'endpoint', 'http_status'])
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency')

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, http_status=response.status_code).inc()
    REQUEST_LATENCY.observe(duration)
    
    return response

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### Log Aggregation

**Using ELK Stack**:

```yaml
# docker-compose.yml
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
    ports:
      - "9200:9200"

  logstash:
    image: logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: kibana:8.11.0
    ports:
      - "5601:5601"
```

## 🔐 Security

### Best Practices

1. **Use environment variables for secrets**
2. **Enable rate limiting**:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/chat")
@limiter.limit("20/minute")
async def chat(request: Request, data: ChatRequest):
    # ... existing code
```

3. **Enable CORS only for specific domains**:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

4. **Use HTTPS everywhere**
5. **Implement API authentication**
6. **Regular security updates**

## 💾 Backup & Recovery

### Database Backup

```bash
# Automated daily backup
#!/bin/bash
# /opt/scripts/backup-db.sh

BACKUP_DIR="/backup/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/slt_chatbot_${DATE}.sql.gz"

# Create backup
docker exec slt-postgres pg_dump -U chatbot slt_chatbot | gzip > "$BACKUP_FILE"

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

# Upload to S3 (optional)
aws s3 cp "$BACKUP_FILE" s3://your-backup-bucket/postgres/
```

### Cron Job

```bash
# Add to crontab
0 2 * * * /opt/scripts/backup-db.sh
```

### Recovery

```bash
# Restore from backup
gunzip -c backup.sql.gz | docker exec -i slt-postgres psql -U chatbot slt_chatbot
```

## 🔄 CI/CD Pipeline

### GitHub Actions

**.github/workflows/deploy.yml**:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and push Docker images
      run: |
        docker build -t slt-backend ./backend
        docker build -t slt-frontend ./frontend
        
    - name: Deploy to production
      run: |
        ssh user@server "cd /opt/slt-chatbot && docker-compose pull && docker-compose up -d"
```

## 📞 Support

For deployment issues:
- Check logs: `docker-compose logs -f`
- Verify environment variables
- Test connectivity to external services
- Review security group/firewall rules

---

**Production Checklist**:
- [ ] SSL certificate configured
- [ ] Environment variables set
- [ ] Database backups automated
- [ ] Monitoring enabled
- [ ] Rate limiting configured
- [ ] Security headers added
- [ ] CORS properly configured
- [ ] Health checks working
- [ ] Logs aggregated
- [ ] Alerts configured
