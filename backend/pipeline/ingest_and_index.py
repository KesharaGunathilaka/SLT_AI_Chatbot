# ingest_and_index.py
import os
import glob
import json
import time
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')


# --- CONFIG ---
MARKDOWN_DIR = "../data/raw"   # folder with page_1.md, page_2.md ...
CHROMA_DIR = "../data/chroma_db"          # local persistence
COLLECTION_NAME = "slt_pages"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"  # sentence-transformers (fast & solid)
CHUNK_SIZE = 800     # tokens ~ words heuristic (you can tune)
CHUNK_OVERLAP = 100  # overlapping characters/words to reduce context loss

# optional: use OpenAI embeddings instead of local model (comment/uncomment)
USE_OPENAI_EMBEDDINGS = False
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # if using OpenAI

# --- helpers ---


def read_markdown(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_text_recursive(text: str, max_chunk_chars=CHUNK_SIZE, overlap_chars=CHUNK_OVERLAP) -> List[str]:
    """
    Simple recursive chunker: tries to split on paragraphs / sentences before splitting by raw window.
    """
    if len(text) <= max_chunk_chars:
        return [text]
    # prefer paragraph split
    parts = text.split("\n\n")
    chunks = []
    buffer = ""
    for p in parts:
        if buffer:
            cand = buffer + "\n\n" + p
        else:
            cand = p
        if len(cand) <= max_chunk_chars:
            buffer = cand
        else:
            if buffer:
                chunks.append(buffer)
            if len(p) > max_chunk_chars:
                # fallback: sentence tokenization
                sents = nltk.sent_tokenize(p)
                t = ""
                for s in sents:
                    if len(t) + len(s) + 1 <= max_chunk_chars:
                        t = t + " " + s if t else s
                    else:
                        if t:
                            chunks.append(t)
                        t = s
                if t:
                    chunks.append(t)
                buffer = ""
            else:
                buffer = p
    if buffer:
        chunks.append(buffer)
    # apply overlap if needed
    if overlap_chars > 0:
        overlapped = []
        for i, c in enumerate(chunks):
            if i == 0:
                overlapped.append(c)
            else:
                prev = overlapped[-1]
                # create overlap from end of prev
                overlap = prev[-overlap_chars:] if len(
                    prev) > overlap_chars else prev
                overlapped.append(overlap + "\n\n" + c)
        return overlapped
    return chunks

# --- main ingestion ---


def ingest_all():
    # create chroma client (local persistence)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # embedding function: sentence-transformers local
    if USE_OPENAI_EMBEDDINGS:
        ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY, model_name="text-embedding-3-small")
        embed_model = None
    else:
        local_model = SentenceTransformer(EMBED_MODEL_NAME)
        # wrapper for chroma: we'll compute embeddings ourselves
        ef = None
        embed_model = local_model

    # create or get collection
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        col = client.get_collection(COLLECTION_NAME)
    else:
        if ef:
            col = client.create_collection(
                name=COLLECTION_NAME, embedding_function=ef)
        else:
            # we'll upsert raw vectors; create collection without embedding function
            col = client.create_collection(name=COLLECTION_NAME)

    doc_files = sorted(glob.glob(os.path.join(MARKDOWN_DIR, "page_*.md")))
    print(f"Found {len(doc_files)} pages to ingest.")
    ids_all, metadatas_all, embeddings_all, documents_all = [], [], [], []

    for path in doc_files:
        page_id = os.path.basename(path)
        raw = read_markdown(path)
        chunks = split_text_recursive(
            raw, max_chunk_chars=CHUNK_SIZE, overlap_chars=CHUNK_OVERLAP)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{page_id}::chunk_{i}"
            metadata = {
                "source_page": page_id,
                "chunk_index": i,
                "path": path,
                "ingest_time": int(time.time()),
            }
            # embed
            if embed_model:
                emb = embed_model.encode(chunk).tolist()
            else:
                emb = ef(chunk)
            ids_all.append(chunk_id)
            metadatas_all.append(metadata)
            embeddings_all.append(emb)
            documents_all.append(chunk)

    # upsert in batches (safety)
    BATCH = 256
    for i in range(0, len(ids_all), BATCH):
        j = min(i+BATCH, len(ids_all))
        col.upsert(
            embeddings=embeddings_all[i:j],
            metadatas=metadatas_all[i:j],
            documents=documents_all[i:j],
            ids=ids_all[i:j]
        )
        print(f"Upserted batch {i}..{j}")

    print("Ingestion complete and persisted.")


if __name__ == "__main__":
    ingest_all()
