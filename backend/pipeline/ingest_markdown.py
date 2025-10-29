import os
import glob
import uuid

import chromadb
from sentence_transformers import SentenceTransformer

from typing import List
import re


def chunk_text(text: str, max_tokens: int = 500, overlap: int = 50) -> List[str]:
    """Chunk text into overlapping segments (approx by words)."""
    words = re.split(r"\s+", text)
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+max_tokens]
        chunks.append(" ".join(chunk))
        i += max_tokens - overlap
    return chunks


# Init ChromaDB
chroma_client = chromadb.PersistentClient(path="slt_chroma_db")
collection = chroma_client.get_or_create_collection("slt_content")

# Embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")


def ingest_markdown_files(raw_dir: str = "../data/raw"):
    """Read scraped Markdown files and insert chunks into ChromaDB."""
    files = glob.glob(os.path.join(raw_dir, "*.md"))
    print(f"📂 Found {len(files)} markdown files in {raw_dir}")

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        # Derive URL if needed from filename (optional: store filepath instead)
        url = os.path.basename(fpath).replace(".md", "")

        # Chunk + embed
        chunks = chunk_text(content)
        embeddings = embedder.encode(chunks, show_progress_bar=True)

        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            collection.add(
                ids=[str(uuid.uuid4())],
                documents=[chunk],
                embeddings=[emb.tolist()],
                metadatas=[{"source": fpath, "chunk": i}]
            )

    print(f"✅ Ingested {len(files)} markdown files into ChromaDB")
