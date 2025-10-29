import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from chromadb.utils import embedding_functions
from groq import Groq

# ---------------------------
# Configurations
# ---------------------------

# Load environment variables (make sure you set GROQ_API_KEY in your .env or system)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "❌ Missing GROQ_API_KEY. Please set it in environment variables.")

# Initialize Flask
app = Flask(__name__)

# Allow requests from frontend (Vite default: localhost:5173)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})

# ---------------------------
# Vector DB (Chroma)
# ---------------------------

# Persistent client stores vectors in ./chroma_db
client = chromadb.PersistentClient(path="chroma_db")

# Use default OpenAI embedding function (you can replace with HuggingFace if offline)
embedding_fn = embedding_functions.DefaultEmbeddingFunction()

# Connect to your collection (should match the name you used in ingest_and_index.py)
collection = client.get_or_create_collection(
    name="slt_docs", embedding_function=embedding_fn)

# ---------------------------
# LLM (Groq)
# ---------------------------
groq_client = Groq(api_key=GROQ_API_KEY)


def query_groq(context, question):
    """Send context + question to Groq model and get response"""
    prompt = f"""
    You are an AI assistant for Sri Lanka Telecom (SLT).
    Use the following context to answer the question as accurately as possible.
    
    Context:
    {context}
    
    Question: {question}
    Answer:
    """
    response = groq_client.chat.completions.create(
        model="llama3-70b-8192",  # you can swap with smaller models if needed
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500,
    )
    return response.choices[0].message.content


# ---------------------------
# API Route
# ---------------------------

@app.route("/query", methods=["POST"])
def query():
    data = request.get_json()
    question = data.get("question", "")

    if not question.strip():
        return jsonify({"answer": "⚠️ Please enter a valid question."}), 400

    # Retrieve top 3 relevant docs from Chroma
    results = collection.query(
        query_texts=[question],
        n_results=3
    )

    # Extract contexts
    contexts = results.get("documents", [[]])[0]
    context_text = "\n\n".join(contexts)

    # Get final answer from Groq
    try:
        answer = query_groq(context_text, question)
    except Exception as e:
        print("❌ Groq error:", e)
        return jsonify({"answer": "⚠️ Error connecting to Groq AI."}), 500

    return jsonify({"answer": answer})


# ---------------------------
# Run Flask
# ---------------------------

if __name__ == "__main__":
    # Make sure this matches frontend (5173)
    app.run(host="0.0.0.0", port=5000, debug=True)
