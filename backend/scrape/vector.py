import json
from sentence_transformers import SentenceTransformer
import chromadb


# Load JSON data
with open("../data/slt.json", "r", encoding="utf-8") as f:
    data = json.load(f)

documents = []
metadatas = []

for i, item in enumerate(data):
    features_text = "\n".join(
        [f"- {feature}" for feature in item.get("features", [])])

    chunk = f"""Name: {item.get('name')}
Connection Type: {item.get('connection_type')}
Data Bundle: {item.get('data_bundle')}
Monthly Rental: Rs. {item.get('monthly_rental')}
Startup Fee: Rs. {item.get('startup_fee')}
Features:
{features_text}
""".strip()

    documents.append(chunk)
    metadatas.append({"plan_name": item.get("name"), "chunk_id": i})


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

print(f"✅ Stored {len(documents)} plans in ChromaDB.")
print("✅ ChromaDB saved to ../chroma_db/")
