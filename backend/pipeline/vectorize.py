# stage2_process_and_vectorize.py
import os
import json
import asyncio
from typing import List, Dict

import aiohttp
import tiktoken
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv

load_dotenv()

# -------- CONFIG --------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
# lighter, cheaper for processing
MODEL = "groq/meta-llama/llama-4-scout-17b-16e-instruct"

CHROMA_DIR = "../data/slt_chroma_db"
COLLECTION_NAME = "slt_content"

# ------------------------

# Tokenizer for safe chunking (using OpenAI's cl100k_base)
tokenizer = tiktoken.get_encoding("cl100k_base")


def chunk_text(text: str, max_tokens: int = 800, overlap: int = 100) -> List[str]:
    """Split text into chunks of max_tokens with overlap."""
    tokens = tokenizer.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunk = tokens[start:end]
        chunks.append(tokenizer.decode(chunk))
        start += max_tokens - overlap
    return chunks


# --------------- CALL GROQ LLM ---------------

async def call_groq_llm(chunk: str) -> str:
    """Send a single chunk to Groq LLM."""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": f"Clean and normalize this text:\n\n{chunk}"}],
        "temperature": 0,
        "max_tokens": 800,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_ENDPOINT, headers=headers, json=data) as resp:
            if resp.status != 200:
                txt = await resp.text()
                print(f"❌ Groq error {resp.status}: {txt}")
                return chunk
            response = await resp.json()
            return response["choices"][0]["message"]["content"]


# --------------- RATE-LIMITED PROCESSING ---------------

async def process_with_llm(text_chunks: List[str]) -> List[str]:
    semaphore = asyncio.Semaphore(3)  # max 3 concurrent
    REQUESTS_PER_MINUTE = 15
    SECONDS_PER_REQUEST = 60 / REQUESTS_PER_MINUTE

    async def send_chunk(chunk):
        async with semaphore:
            await asyncio.sleep(SECONDS_PER_REQUEST)
            return await call_groq_llm(chunk)

    tasks = [send_chunk(chunk) for chunk in text_chunks]
    return await asyncio.gather(*tasks)


# --------------- VECTORIZE & SAVE TO CHROMA ---------------

def vectorize_and_store(chunks: List[str], metadata: List[Dict]):
    """Embed chunks and insert into ChromaDB."""
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Init Chroma
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    for i, chunk in enumerate(chunks):
        embedding = model.encode(chunk).tolist()
        collection.add(
            ids=[f"chunk_{i}"],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[metadata[i]]
        )

    print(f"✅ Stored {len(chunks)} chunks into ChromaDB")


# --------------- MAIN PIPELINE ---------------

async def main():
    # Load crawled data
    with open("../data/slt_raw.json", "r", encoding="utf-8") as f:
        pages = json.load(f)

    all_chunks, metadata = [], []
    for page in pages:
        url, content = page["url"], page["content"]
        chunks = chunk_text(content)
        all_chunks.extend(chunks)
        metadata.extend([{"url": url}] * len(chunks))

    print(f"📝 Total {len(all_chunks)} chunks generated")

    # Process with LLM (rate-limited)
    processed_chunks = await process_with_llm(all_chunks)

    # Store into Chroma
    vectorize_and_store(processed_chunks, metadata)


if __name__ == "__main__":
    asyncio.run(main())
