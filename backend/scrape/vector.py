import json
from sentence_transformers import SentenceTransformer
import chromadb

# Load JSON data (full site scrape)
with open("../data/slt_full_sitemap.json", "r", encoding="utf-8") as f:
    data = json.load(f)

documents = []
metadatas = []

for i, item in enumerate(data):
    # Format features list
    features_text = "\n".join(
        [f"- {feature}" for feature in item.get("features", [])]
    )

    # Format pricing list
    pricing_text = "\n".join(
        [f"- {p.get('amount', '')} {p.get('currency', '')} ({p.get('billing', '')})"
         for p in item.get("pricing", [])]
    )

    # Format requirements list
    requirements_text = "\n".join(
        [f"- {req}" for req in item.get("requirements", [])]
    )

    # Format contact info
    contact_text = "\n".join(
        [f"- {contact}" for contact in item.get("contact_info", [])]
    )

    # Create a unified chunk for all page types
    chunk = f"""
Title: {item.get('title', '')}
Category: {item.get('category', '')}
Description: {item.get('description', '')}

Details:
{item.get('details', '')}

Features:
{features_text if features_text else '- None'}

Pricing:
{pricing_text if pricing_text else '- None'}

Requirements:
{requirements_text if requirements_text else '- None'}

Contact Info:
{contact_text if contact_text else '- None'}

Source URL: {item.get('source_url', '')}
""".strip()

    documents.append(chunk)
    metadatas.append({
        "title": item.get("title", ""),
        "category": item.get("category", ""),
        "chunk_id": i,
        "source_url": item.get("source_url", "")
    })

# Load embedding model
model = SentenceTransformer("BAAI/bge-base-en")

# Create embeddings
embeddings = model.encode(documents, show_progress_bar=True)

# Store in ChromaDB
client = chromadb.PersistentClient(path="../chroma_db")
collection = client.get_or_create_collection(name="slt_chunks")

for i, (doc, embedding, metadata) in enumerate(zip(documents, embeddings, metadatas)):
    collection.add(
        documents=[doc],
        embeddings=[embedding.tolist()],
        ids=[str(i)],
        metadatas=[metadata]
    )

print(f"✅ Stored {len(documents)} documents in ChromaDB.")
print("✅ ChromaDB saved to ../chroma_db/")
