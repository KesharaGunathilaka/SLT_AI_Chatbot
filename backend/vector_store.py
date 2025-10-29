import chromadb
from sentence_transformers import SentenceTransformer

chroma_client = chromadb.PersistentClient(path="chroma_db")  # ✅ Persistent
collection = chroma_client.get_or_create_collection("slt_data")
embedder = SentenceTransformer("all-MiniLM-L6-v2")


def index_data(pages):
    for url, content in pages.items():
        doc = content.get("text", "")
        if not doc.strip():
            continue
        embedding = embedder.encode([doc])[0]
        collection.add(documents=[doc], embeddings=[embedding], ids=[url])


def query_similar_docs(query, top_k=3):
    embedding = embedder.encode([query])[0]
    results = collection.query(query_embeddings=[embedding], n_results=top_k)
    return results
