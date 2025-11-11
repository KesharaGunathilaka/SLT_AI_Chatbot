import os
import time
import asyncio
from typing import List, Dict, Any
import asyncpg
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from pymilvus import (connections, FieldSchema, CollectionSchema, DataType, Collection, utility)

# Postgres connection settings
DATABASE_URL = os.getenv("DATABASE_URL")

COLLECTION_NAME = os.getenv("VECTOR_COLLECTION")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

BATCH_SIZE = int(os.getenv("EMBED_BATCH", 32))
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Postgres
async def create_pg_pool():
    return await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=20)

async def fetch_pages_to_vectorize(pool, limit: int = 500):
    query = """
    SELECT page_id::text, name, url, canonical_url, category, priority, current_version_id::text, last_updated_at, cleaned_content, raw_content
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

# Markdown Header Split
Markdown_Splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
        ("#####", "Header 5"),
        ]
)

# Semantic Chunking Split
Embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
Semantic_Splitter = SemanticChunker(
    embeddings=Embeddings,
    breakpoint_threshold_type="percentile",  # or gradient
    breakpoint_threshold_amount=90,
    sentence_split_regex=r'\n\s*\n'
)

# Size-based Splitter
Size_Splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)

#Milvus connection
def connect_milvus():
    connections.connect(
        alias="default",
        host="localhost",
        port="19530"
    )
    print("✅ Connected to Local Milvus at localhost:19530")


def create_collection_if_not_exists():
    if utility.has_collection(COLLECTION_NAME):
        print("Collection exists:", COLLECTION_NAME)
        return Collection(COLLECTION_NAME)

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),        
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="page_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="version_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="canonical_url", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="priority", dtype=DataType.DOUBLE),
        FieldSchema(name="last_updated_at", dtype=DataType.INT64),
        FieldSchema(name="chunk_index", dtype=DataType.INT64),
        FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=4096),
        
    ]
    schema = CollectionSchema(fields, description="SLT website chunks")
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

def get_text_chunks(text: str) -> List[str]:
    """
    Hybrid splitter:
    1. Split text by Markdown headers to keep sections together.
    2. Within each section, use SemanticChunker for meaning-based segmentation.
    """    

    markdown_chunks = Markdown_Splitter.split_text(text)

    final_chunks = []
    for doc in markdown_chunks:
        clean_text = doc.page_content.strip()
        if not clean_text or len(clean_text) < 50:
            continue  # skip too short fragments

        # Split large sections semantically, keep small ones as-is
        semantic_docs = Semantic_Splitter.create_documents([clean_text])
        
        for sem_doc in semantic_docs:
            sem_text = sem_doc.page_content.strip()
            if len(sem_text) > 1000:
                size_docs = Size_Splitter.split_documents([sem_doc])
                for s in size_docs:
                    final_chunks.append(s.page_content.strip())
            else:
                final_chunks.append(sem_text)

    return final_chunks

# embed with sentence-transformers
def load_embedding_model():
    model = SentenceTransformer(EMBEDDING_MODEL)
    return model

def embed_texts(model, texts: List[str]) -> List[List[float]]:
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=BATCH_SIZE, convert_to_numpy=True)
    return [e.tolist() for e in embeddings]

# Upsert / delete helpers for Milvus
def upsert_vectors(collection: Collection, vectors: List[Dict[str, Any]]):
    # vectors: list of dicts with keys matching fields
    # build columns in order: id, embedding, page_id, version_id, url, canonical_url, category, priority, tags, chunk_index, chunk_text, last_updated_at
    ids = [v["id"] for v in vectors]
    embeddings = [v["embedding"] for v in vectors]
    page_ids = [v["page_id"] for v in vectors]
    names = [v.get("name") or "" for v in vectors]
    version_ids = [v["version_id"] for v in vectors]
    urls = [v["url"] for v in vectors]
    canonical_urls = [v.get("canonical_url") or "" for v in vectors]
    categories = [v.get("category") or "" for v in vectors]
    priorities = [v.get("priority") or 0.0 for v in vectors]
    last_updated_ts = [int(v.get("last_updated_at", int(time.time()))) for v in vectors]
    chunk_indices = [v["chunk_index"] for v in vectors]
    chunk_texts = [v["chunk_text"][:4096] for v in vectors]  # truncate if too long
    

    entities = [
        ids,
        embeddings,
        page_ids,
        names,
        version_ids,
        urls,
        canonical_urls,
        categories,
        priorities,
        last_updated_ts,
        chunk_indices,
        chunk_texts
    ]
    collection.insert(entities)
    collection.flush()

def delete_vectors_by_page(collection: Collection, page_id: str):
    expr = f'page_id == "{page_id}"'
    collection.delete(expr)
    collection.flush()


async def get_inactive_page_ids(pool):
    """Fetch all inactive page IDs from Postgres."""
    query = "SELECT page_id::text FROM pages WHERE is_active = FALSE"
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [row["page_id"] for row in rows]


def delete_inactive_pages_from_milvus(collection, page_ids: list[str]):
    """Delete all inactive pages from Milvus based on page_id."""
    if not page_ids:
        print(" No inactive pages found in Postgres.")
        return

    print(f" Found {len(page_ids)} inactive pages. Deleting from Milvus...")

    # Delete in batches for efficiency
    batch_size = 100
    for i in range(0, len(page_ids), batch_size):
        batch = page_ids[i:i+batch_size]
        expr = f"page_id in [{', '.join(f'\"{x}\"' for x in batch)}]"
        collection.delete(expr)
        collection.flush()

    print("✅ Cleanup completed — inactive pages removed from Milvus.")

# Process a single page
async def process_one_page(pool, collection, model, row):
    """
    row contains: page_id, name, url, canonical_url, category, priority, cleaned_content, raw_content, current_version_id, last_updated_at
    """
    page_id = row["page_id"]
    name = row["name"] or ""
    url = row["url"]
    canonical_url = row["canonical_url"] or ""
    category = row["category"] or "General"
    priority = float(row["priority"] or 0.0)
    cleaned_content = row["cleaned_content"] or ""
    raw_content = row["raw_content"] or ""
    version_id = row["current_version_id"] or ""
    last_updated_at = row["last_updated_at"]
    last_updated_ts = int(last_updated_at.timestamp()) if last_updated_at else int(time.time())

    if not raw_content.strip():
        print(f"Skip empty content for page {page_id}")
        await mark_page_vectorized(pool, page_id)  # mark as done to avoid repeated attempts
        return

    # If there are old vectors for this page (maybe previous version), delete them first
    delete_vectors_by_page(collection, page_id)

    # Combine both cleaned_content and raw_content for chunking
    combined_content = ""
    if cleaned_content.strip():
        combined_content += f"CLEANED CONTENT:\n{cleaned_content}\n\n"
    if raw_content.strip():
        combined_content += f"RAW CONTENT:\n{raw_content}"

    # Chunk content
    chunks = get_text_chunks(combined_content)
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
                "name": name,
                "version_id": version_id,
                "url": url,
                "canonical_url": canonical_url,
                "category": category,
                "priority": priority,
                "chunk_index": chunk_idx,
                "chunk_text": batch_chunks[j],
                "last_updated_at": last_updated_ts
            })

    # Upsert to Milvus
    upsert_vectors(collection, vectors_to_insert)
    # Mark page vectorized
    await mark_page_vectorized(pool, page_id)
    print(f"Vectorized page {page_id} with {len(chunks)} chunks.")


async def main_loop(limit_each_run: int = 500):
    
    start = time.time()

    # Connect PG
    pool = await create_pg_pool()
    # Connect Milvus
    connect_milvus()
    collection = create_collection_if_not_exists()
    model = await asyncio.to_thread(load_embedding_model)

    # Step 1: Cleanup inactive pages first
    print("\n===== Starting Cleanup of Inactive Pages =====")
    inactive_page_ids = await get_inactive_page_ids(pool)
    delete_inactive_pages_from_milvus(collection, inactive_page_ids)
    print("===== Cleanup Completed =====\n")

    # Step 2: Proceed with new vectorization
    try:
        while True:
            rows = await fetch_pages_to_vectorize(pool, limit_each_run)
            if not rows:
                print("No pages to vectorize. Exiting.")
                break
            # process pages sequentially or in parallel (be careful with model memory)
            for row in rows:
                await process_one_page(pool, collection, model, row)

    finally:
        await pool.close()
    
    print("===== Vectorization Completed =====")
    print(f"Total time: {time.time() - start:.2f} seconds")
    

if __name__ == "__main__":
    asyncio.run(main_loop(limit_each_run=50))
