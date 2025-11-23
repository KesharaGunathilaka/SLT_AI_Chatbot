import streamlit as st
import os
import re
import math
import time
import numpy as np
from typing import List, Dict, Optional, Any
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection
from rank_bm25 import BM25Okapi

# Import your existing LLM function (Ensure llm_model.py is in the same folder)
try:
    from llm_model import query_llm
except ImportError:
    st.error("llm_model.py not found. Please upload it.")

# Optional Dependencies
try:
    from FlagEmbedding import FlagReranker
    FLAG_RERANK = True
except Exception:
    FLAG_RERANK = False
try:
    from sentence_transformers import CrossEncoder
    CROSS_ENC = True
except Exception:
    CROSS_ENC = False

# --- CONFIGURATION ---
st.set_page_config(page_title="SLT AI Assistant", layout="wide")

# Constants
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION", "SLT_AI")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "30"))
CONTEXT_CHUNKS = int(os.getenv("CONTEXT_CHUNKS", "5"))
RERANK_TOP_K = 20

# --- CACHED RESOURCES (Run once) ---


@st.cache_resource
def load_resources():
    """Loads models and connects to Milvus only once."""
    status_text = st.empty()
    status_text.info("Connecting to Milvus and loading models...")

    # 1. Connect to Milvus
    uri = st.secrets["ZILLIZ_CLOUD_URI"]
    token = st.secrets["ZILLIZ_CLOUD_API_KEY"]

    try:
        connections.connect(alias="default", uri=uri, token=token)
        collection = Collection(COLLECTION_NAME)
        collection.load()
    except Exception as e:
        st.error(f"Milvus Connection Error: {e}")
        return None, None, None, None, None

    # 2. Build BM25 Index
    # Note: In production, you should save/load the index from disk,
    # but for this demo, we rebuild it on startup.
    docs = []
    urls = []
    # Limit to avoid timeouts on free cloud tiers
    results = collection.query(expr="", output_fields=[
                               "chunk_text", "url"], limit=10000)
    for r in results:
        text = r.get("chunk_text")
        if text:
            docs.append(text)
            urls.append(r.get("url", ""))

    bm25_index = None
    if docs:
        tokenized_corpus = [re.findall(r'\w+', doc.lower()) for doc in docs]
        bm25_index = BM25Okapi(tokenized_corpus)

    # 3. Load Embedder
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    # 4. Load Reranker
    reranker = None
    reranker_prov = "none"
    if FLAG_RERANK:
        try:
            # fp16 False for CPU compatibility
            reranker = FlagReranker("BAAI/bge-reranker-base", use_fp16=False)
            reranker_prov = "flag"
        except:
            pass
    elif CROSS_ENC:
        reranker = CrossEncoder("BAAI/bge-reranker-base")
        reranker_prov = "cross"

    status_text.empty()
    return collection, bm25_index, docs, urls, embedder, reranker, reranker_prov


# Load resources
collection, bm25_index, bm25_docs, bm25_urls, embedder, reranker, reranker_prov = load_resources()

# --- HELPER FUNCTIONS ---


def embed_query(q: str) -> List[float]:
    return embedder.encode([q])[0].tolist()


def milvus_search(vec: List[float], k: int) -> List[Dict]:
    search_params = {"metric_type": "IP", "params": {"nprobe": 15}}
    res = collection.search(
        data=[vec], anns_field="embedding", param=search_params,
        limit=k, output_fields=["chunk_text", "priority",
                                "last_updated_at", "url", "category"]
    )
    hits = []
    for hit in res[0]:
        ent = hit.entity
        base = float(hit.distance)
        if base < 0.25:
            continue  # Threshold

        # Simple Boost logic (simplified for Streamlit)
        boosted = base
        if getattr(ent, "priority", None):
            boosted += 0.001 * min(getattr(ent, "priority"), 100)

        hits.append({
            "text": getattr(ent, "chunk_text", ""),
            "url": getattr(ent, "url", ""),
            "score": base,
            "boosted": boosted,
        })
    return sorted(hits, key=lambda x: x["boosted"], reverse=True)


def bm25_search(query: str, k: int = 10) -> List[Dict]:
    if not bm25_index:
        return []
    tokens = re.findall(r'\w+', query.lower())
    scores = bm25_index.get_scores(tokens)
    top_indices = sorted(range(len(scores)),
                         key=lambda i: scores[i], reverse=True)[:k]
    return [
        {
            "text": bm25_docs[i],
            "url": bm25_urls[i],
            "score": float(scores[i]),
            "boosted": float(scores[i])
        }
        for i in top_indices if scores[i] > 0
    ]


def rerank_logic(query: str, cands: List[Dict], top_k: int) -> List[Dict]:
    if not cands or not reranker:
        return sorted(cands, key=lambda x: x["boosted"], reverse=True)[:top_k]

    pairs = [(query, c["text"]) for c in cands]
    try:
        if reranker_prov == "flag":
            scores = reranker.compute_score(pairs, normalize=True)
        else:
            scores = reranker.predict(pairs)

        for c, s in zip(cands, scores):
            c["rerank"] = float(s)
        return sorted(cands, key=lambda x: x.get("rerank", x["boosted"]), reverse=True)[:top_k]
    except Exception:
        return sorted(cands, key=lambda x: x["boosted"], reverse=True)[:top_k]


def generate_answer(q: str, ctxs: List[Dict], history: List[Dict]) -> Dict[str, str]:
    # Format Context
    formatted_ctx = []
    for i, c in enumerate(ctxs):
        url = c.get("url", "No URL")
        formatted_ctx.append(f"Source [{i+1}] (URL: {url}):\n{c['text']}")
    context_str = "\n\n".join(formatted_ctx)

    # Format History
    history_str = ""
    # Convert Streamlit session state history to string
    if history:
        # Get last 6 messages
        recent = history[-6:]
        history_str = "Prior Conversation:\n"
        for msg in recent:
            role = "User" if msg["role"] == "user" else "AI"
            history_str += f"{role}: {msg['content']}\n"

    prompt = f"""
You are an expert ISP consultant for Sri Lanka Telecom (SLT).
Answer based ONLY on the Context and History.

{history_str}
Context:
{context_str}

User Question: {q}

Instructions:
1. Identify Intent: If user says "data", they usually mean Broadband. Don't push LMS/Education plans unless asked.
2. Answer concisely.
3. STRICTLY provide exactly TWO source URLs at the bottom.
4. Generate a follow-up question.

Output Format:
[Answer]

**Sources:**
* [URL]
* [URL]

**Next Suggestion:**
[Single Question]
"""
    full_resp = query_llm(prompt).strip()

    # Parse Logic
    reply_text = full_resp
    next_sugg = "Try asking about coverage?"

    if "**Next Suggestion:**" in full_resp:
        parts = full_resp.split("**Next Suggestion:**")
        reply_text = parts[0].strip()
        if len(parts) > 1:
            next_sugg = parts[1].strip().replace("*", "").strip()

    return {"reply": reply_text, "next_suggestion": next_sugg}

# --- UI LOGIC ---


st.title("📡 SLT AI Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Ask about packages, coverage, or support..."):
    # 1. Show User Message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. Logic (Silent Augmentation)
    search_q = prompt
    if "data" in prompt.lower() and "broadband" not in prompt.lower():
        search_q = f"{prompt} broadband connection packages"

    # 3. Search Processing
    with st.spinner("Searching SLT database..."):
        qvec = embed_query(search_q)
        sem_res = milvus_search(qvec, SEARCH_TOP_K)
        key_res = bm25_search(search_q, k=20)

        # Hybrid Merge (Alpha 0.6)
        alpha = 0.6
        max_bm = max((k["boosted"] for k in key_res), default=1.0)

        combined = []
        for r in sem_res:
            r["combined"] = alpha * r["boosted"]
            combined.append(r)
        for k in key_res:
            k["combined"] = (1 - alpha) * (k["boosted"] / max_bm)
            combined.append(k)

        # Dedup
        seen = set()
        final_cands = []
        for c in sorted(combined, key=lambda x: x["combined"], reverse=True):
            if c["text"] not in seen:
                seen.add(c["text"])
                final_cands.append(c)

        # Rerank & Select
        reranked = rerank_logic(
            prompt, final_cands[:RERANK_TOP_K], RERANK_TOP_K)
        top_chunks = reranked[:CONTEXT_CHUNKS]

    # 4. Generate Answer
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            ans = generate_answer(prompt, top_chunks,
                                  st.session_state.messages)
            st.markdown(ans["reply"])
            if ans["next_suggestion"]:
                st.info(f" Suggestion: {ans['next_suggestion']}")

    st.session_state.messages.append(
        {"role": "assistant", "content": ans["reply"]})
