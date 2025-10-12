import os
import time
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any
import asyncpg
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pymilvus import (
    connections,
    FieldSchema, CollectionSchema, DataType, Collection, utility
)

DATABASE_URL = os.getenv("DATABASE_URL")

# Zilliz Cloud / Milvus connection settings
URI = os.getenv("ZILLIZ_CLOUD_URI")
TOKEN = os.getenv("ZILLIZ_CLOUD_API_KEY")

COLLECTION_NAME = os.getenv("VECTOR_COLLECTION")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
EMBEDDING_DIM = 1024

BATCH_SIZE = int(os.getenv("EMBED_BATCH", 32))
CHUNK_SIZE = 1000        # target characters per chunk (langchain splitter uses chars not tokens)
CHUNK_OVERLAP = 200

# Postgres
async def create_pg_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)

async def fetch_pages_to_vectorize(pool, limit: int = 100):
    # select pages with is_vectorized = false and active
    query = """
    SELECT page_id::text, url, canonical_url, category, priority, tags, content_md, current_version_id::text, last_updated_at
    FROM pages
    WHERE is_active = TRUE AND is_vectorized = FALSE
    ORDER BY last_updated_at DESC NULLS LAST
    LIMIT $1
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, limit)
    return rows

async def mark_page_vectorized(pool, page_id: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE pages SET is_vectorized = TRUE WHERE page_id = $1", page_id)

async def mark_page_unvectorized(pool, page_id: str):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE pages SET is_vectorized = FALSE WHERE page_id = $1", page_id)

#Milvus connection
def connect_milvus():
    uri = URI
    token = TOKEN

    if not uri or not token:
        raise ValueError(
            "Missing ZILLIZ_CLOUD_URI or ZILLIZ_CLOUD_API_KEY environment variables")

    connections.connect(
        alias="default",
        uri=uri,
        token=token,
    )
    print(f"✅ Connected to Zilliz Cloud at {uri}")


def create_collection_if_not_exists():
    if utility.has_collection(COLLECTION_NAME):
        print("Collection exists:", COLLECTION_NAME)
        return Collection(COLLECTION_NAME)

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="page_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="version_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="canonical_url", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="priority", dtype=DataType.DOUBLE),
        FieldSchema(name="tags", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
        FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="last_updated_at", dtype=DataType.INT64),
    ]
    schema = CollectionSchema(fields, description="SLT site page chunks")
    collection = Collection(name=COLLECTION_NAME, schema=schema, consistency_level="Session")
    # Create index for embeddings
    index_params = {
        "metric_type": "IP",   # or "L2" (choose depending on vector normalization)
        "index_type": "IVF_FLAT",
        "params": {"nlist": 1024}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()
    return collection


# Chunking & Embedding
def get_text_chunks(text: str) -> List[str]:
    # Use langchain RecursiveCharacterTextSplitter for semantic splitting
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    return splitter.split_text(text)

# embed with sentence-transformers in thread to avoid blocking event loop
def load_embedding_model():
    model = SentenceTransformer(EMBEDDING_MODEL)
    return model

def embed_texts(model, texts: List[str]) -> List[List[float]]:
    # returns list of embeddings (list of floats)
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=BATCH_SIZE, convert_to_numpy=True)
    # convert numpy arrays to python lists
    return [e.tolist() for e in embeddings]

# Upsert / delete helpers for Milvus
def upsert_vectors(collection: Collection, vectors: List[Dict[str, Any]]):
    # vectors: list of dicts with keys matching fields
    # build columns in order: id, embedding, page_id, version_id, url, canonical_url, category, priority, tags, chunk_index, chunk_text, last_updated_at
    ids = [v["id"] for v in vectors]
    embeddings = [v["embedding"] for v in vectors]
    page_ids = [v["page_id"] for v in vectors]
    version_ids = [v["version_id"] for v in vectors]
    urls = [v["url"] for v in vectors]
    canonical_urls = [v.get("canonical_url") or "" for v in vectors]
    categories = [v.get("category") or "" for v in vectors]
    priorities = [v.get("priority") or 0.0 for v in vectors]
    tags = [json.dumps(v.get("tags") or []) for v in vectors]  # store tags as JSON string
    chunk_indices = [v["chunk_index"] for v in vectors]
    chunk_texts = [v["chunk_text"][:4096] for v in vectors]  # truncate if too long
    last_updated_ts = [int(v.get("last_updated_at", int(time.time()))) for v in vectors]

    entities = [
        ids,
        embeddings,
        page_ids,
        version_ids,
        urls,
        canonical_urls,
        categories,
        priorities,
        tags,
        chunk_indices,
        chunk_texts,
        last_updated_ts
    ]
    collection.insert(entities)
    collection.flush()  # ensure persistence

def delete_vectors_by_page(collection: Collection, page_id: str):
    expr = f'page_id == "{page_id}"'
    collection.delete(expr)
    collection.flush()

# Orchestration
async def process_one_page(pool, collection, model, row):
    """
    row contains: page_id, url, canonical_url, category, priority, tags, content_md, current_version_id, last_updated_at
    """
    page_id = row["page_id"]
    url = row["url"]
    canonical_url = row["canonical_url"] or ""
    category = row["category"] or "General"
    priority = float(row["priority"] or 0.0)
    tags = row["tags"] or []
    content_md = row["content_md"] or ""
    version_id = row["current_version_id"] or ""
    last_updated_at = row["last_updated_at"]
    last_updated_ts = int(last_updated_at.timestamp()) if last_updated_at else int(time.time())

    if not content_md.strip():
        print(f"Skip empty content for page {page_id}")
        await mark_page_vectorized(pool, page_id)  # mark as done to avoid repeated attempts
        return

    # If there are old vectors for this page (maybe previous version), delete them first
    delete_vectors_by_page(collection, page_id)

    # Chunk content
    chunks = get_text_chunks(content_md)
    if not chunks:
        print(f"No chunks for {page_id}")
        await mark_page_vectorized(pool, page_id)
        return

    # Embed in batches
    vectors_to_insert = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i: i + BATCH_SIZE]
        # run embedding in thread
        embeddings = await asyncio.to_thread(embed_texts, model, batch_chunks)
        for j, emb in enumerate(embeddings):
            chunk_idx = i + j
            vid = f"{page_id}_{version_id}_{chunk_idx}"
            vectors_to_insert.append({
                "id": vid,
                "embedding": emb,
                "page_id": page_id,
                "version_id": version_id,
                "url": url,
                "canonical_url": canonical_url,
                "category": category,
                "priority": priority,
                "tags": tags,
                "chunk_index": chunk_idx,
                "chunk_text": batch_chunks[j],
                "last_updated_at": last_updated_ts
            })

    # Upsert to Milvus
    upsert_vectors(collection, vectors_to_insert)
    # Mark page vectorized
    await mark_page_vectorized(pool, page_id)
    print(f"Vectorized page {page_id} with {len(chunks)} chunks.")


async def main_loop(limit_each_run: int = 100):
    # Connect PG
    pool = await create_pg_pool()
    # Connect Milvus
    connect_milvus()
    collection = create_collection_if_not_exists()
    # load embedding model (runs on CPU by default; use GPU if available)
    model = await asyncio.to_thread(load_embedding_model)

    try:
        while True:
            rows = await fetch_pages_to_vectorize(pool, limit_each_run)
            if not rows:
                print("No pages to vectorize. Exiting.")
                break
            # process pages sequentially or in parallel (be careful with model memory)
            for row in rows:
                await process_one_page(pool, collection, model, row)
            # loop again to pick up new pages
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main_loop(limit_each_run=50))
