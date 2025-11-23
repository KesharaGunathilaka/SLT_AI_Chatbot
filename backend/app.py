import os
import re
import math
import asyncio
import numpy as np
from typing import List, Dict, Optional, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection
from rank_bm25 import BM25Okapi
from llm_model import query_llm

# Optional Dependency Handling
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


# CONFIG
URI = os.getenv("ZILLIZ_CLOUD_URI")
TOKEN = os.getenv("ZILLIZ_CLOUD_API_KEY")
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION", "SLT_AI")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")

# Milvus Search Configuration
SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "30"))
CONTEXT_CHUNKS = int(os.getenv("CONTEXT_CHUNKS", "5"))
SCORE_THRESHOLD_IP = float(os.getenv("SCORE_THRESHOLD_IP", "0.25"))

# Metadata Boosting Configuration
PRIORITY_BONUS = float(os.getenv("PRIORITY_BONUS", "0.001"))
RECENCY_BONUS = float(os.getenv("RECENCY_BONUS", "0.03"))
RECENCY_HALF_LIFE_DAYS = float(os.getenv("RECENCY_BONUS_HALF_LIFE_DAYS", "60"))

# Multi-Query Expansion (MQE) Configuration
ENABLE_MQE = os.getenv("ENABLE_MQE", "true").lower() == "true"
MQE_QUERIES = int(os.getenv("MQE_QUERIES", "2"))

# Reranking Configuration
ENABLE_RERANK = os.getenv("ENABLE_RERANK", "true").lower() == "true"
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "20"))

# FastAPI
app = FastAPI(title="SLT AI Chatbot", version="2.4")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# MILVUS CONNECTION


@app.on_event("startup")
async def startup_event():
    # connect and load collection (guard with try/except)
    try:
        connections.connect(alias="default", uri=URI, token=TOKEN)
        global collection
        collection = Collection(COLLECTION_NAME)
        collection.load()
        await asyncio.to_thread(build_bm25_index, collection)
        print("Startup complete: Milvus loaded and BM25 built.")
    except Exception as e:
        print("Startup error:", e)
        raise

# MODELS 
embedder = SentenceTransformer(EMBEDDING_MODEL)
_reranker = None
_reranker_provider = "none"

# RERANKER INITIALIZATION
def ensure_reranker():
    global _reranker, _reranker_provider
    if not ENABLE_RERANK or _reranker is not None:
        return _reranker, _reranker_provider
    if FLAG_RERANK:
        try:
            _reranker = FlagReranker(RERANK_MODEL, use_fp16=True)
            _reranker_provider = "flag"
            return _reranker, _reranker_provider
        except Exception:
            pass
    if CROSS_ENC:
        _reranker = CrossEncoder(RERANK_MODEL)
        _reranker_provider = "cross"
    return _reranker, _reranker_provider


def embed_query(q: str) -> List[float]:
    return embedder.encode([q])[0].tolist()

# Metadata Boosting
def apply_metadata_boost(score: float, priority: Optional[float], ts: Optional[int]) -> float:
    s = score
    if priority:
        s += PRIORITY_BONUS * min(max(priority, 0), 100)
    if ts:
        age_days = max(0.0, (time.time() - ts) / 86400)
        recency = math.exp(-math.log(2) * age_days / RECENCY_HALF_LIFE_DAYS)
        s += RECENCY_BONUS * recency
    return s


def milvus_search(vec: List[float], k: int) -> List[Dict[str, Any]]:
    search_params = {"metric_type": "IP", "params": {"nprobe": 15}}
    res = collection.search(
        data=[vec], anns_field="embedding", param=search_params,
        limit=k, output_fields=["chunk_text", "priority", "last_updated_at", "url", "category"]
    )
    hits = []
    for hit in res[0]:
        ent = hit.entity
        base = float(hit.distance)
        if base < SCORE_THRESHOLD_IP:
            continue
        boosted = apply_metadata_boost(base,
                                       getattr(ent, "priority", None),
                                       getattr(ent, "last_updated_at", None))
        hits.append({
            "text": getattr(ent, "chunk_text", ""),
            "url": getattr(ent, "url", ""),
            "category": getattr(ent, "category", ""),
            "score": base,
            "boosted": boosted,
        })
    return sorted(hits, key=lambda x: x["boosted"], reverse=True)


# BM25 KEYWORD SEARCH
bm25_index = None
bm25_docs = []
bm25_urls = []


def build_bm25_index(collection: Collection, limit: int = 100000):
    global bm25_index, bm25_docs, bm25_urls
    print("Building BM25 keyword index (once at startup)...")
    # Query Milvus in pages to avoid memory spikes
    batch = 10000
    offset = 0
    docs = []
    urls = []
    while True:
        try:
            results = collection.query(
                expr="", output_fields=["chunk_text", "url"], limit=batch, offset=offset)
        except TypeError:
            # older pymilvus doesn't support offset — read once with larger limit
            results = collection.query(
                output_fields=["chunk_text", "url"], limit=limit)
            offset = 0
        if not results:
            break
        for r in results:
            text = r.get("chunk_text")
            if text:
                docs.append(text)
                urls.append(r.get("url", ""))
        if len(results) < batch:
            break
        offset += batch
        if offset >= limit:
            break

    bm25_docs = docs
    bm25_urls = urls
    tokenized_corpus = [re.findall(r'\w+', doc.lower()) for doc in bm25_docs]
    if tokenized_corpus:
        bm25_index = BM25Okapi(tokenized_corpus)
        print(f"BM25 index built with {len(bm25_docs)} chunks.")
    else:
        print("BM25 index empty (no docs found).")


def bm25_search(query: str, k: int = 10) -> List[Dict[str, Any]]:
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
            "category": "keyword_match",
            "score": float(scores[i]),
            "boosted": float(scores[i])
        }
        for i in top_indices if scores[i] > 0
    ]


# MULTI-QUERY EXPANSION
async def multi_query_expand(q: str, n: int) -> List[str]:
    if n <= 0:
        return []
    prompt = f"Generate {n} short paraphrases or related questions for: {q}\nReturn each on a new line."
    try:
        resp = query_llm(prompt)
        lines = [l.strip("-• \t") for l in resp.splitlines() if l.strip()]
        uniq, out = set(), []
        for l in lines:
            if l not in uniq:
                uniq.add(l)
                out.append(l)
            if len(out) >= n:
                break
        return out
    except Exception:
        return []

# RERANKING
def rerank(query: str, cands: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    if not cands:
        return []
    model, prov = ensure_reranker()
    if not model:
        return sorted(cands, key=lambda x: x["boosted"], reverse=True)[:top_k]
    pairs = [(query, c["text"]) for c in cands]
    try:
        scores = model.compute_score(
            pairs, normalize=True) if prov == "flag" else model.predict(pairs)
        for c, s in zip(cands, scores):
            c["rerank"] = float(s)
        return sorted(cands, key=lambda x: x.get("rerank", x["boosted"]), reverse=True)[:top_k]
    except Exception:
        return sorted(cands, key=lambda x: x["boosted"], reverse=True)[:top_k]


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def select_diverse_chunks(chunks: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    if len(chunks) <= top_n:
        return chunks[:]
    texts = [c.get("text", "") for c in chunks]
    embeddings = embedder.encode(texts, convert_to_numpy=True)
    chosen = []
    chosen_embs = []
    for idx, c in enumerate(chunks):
        emb = embeddings[idx]
        if not chosen_embs:
            chosen.append(c)
            chosen_embs.append(emb)
        else:
            max_sim = max(cosine_sim(emb, ce) for ce in chosen_embs)
            if max_sim < 0.85:  # diversity threshold
                chosen.append(c)
                chosen_embs.append(emb)
        if len(chosen) >= top_n:
            break
    if len(chosen) < top_n:
        return chunks[:top_n]
    return chosen


# GENERATE ANSWER
def generate_answer(q: str, ctxs: List[Dict[str, Any]], history: List[str]) -> Dict[str, str]:
    formatted_ctx = []
    unique_urls = []
    for i, c in enumerate(ctxs):
        url = c.get("url", "")
        if url not in unique_urls:
            unique_urls.append(url)

        formatted_ctx.append(f"Source [{i+1}] (URL: {url}):\n{c['text']}")

    context_str = "\n\n".join(formatted_ctx)
    history_str = ""
    if history:
        history_entries = history[-6:]
        history_str = "Conversation History:\n" + "\n".join(history_entries) + "\n"

    prompt = f"""
You are an expert ISP consultant for Sri Lanka Telecom.
Use the Context and History below to answer.

{history_str}
Context:
{context_str}

User Question: {q}

1. Give a concise, correct answer.
2. STRICTLY provide exactly TWO most relevant source URLs at the bottom.
3. Give follow up questions according to given context, answer and history.

Format:
[Your Answer Here]

**Sources:**
* <source-url-1>
* <source-url-2>

**Next Suggestion:**
* <question-1>
* <question-2>
"""
    resp = query_llm(prompt)
    return {
        "reply": resp.strip(),
        "next_suggestion": "Would you like to know more about related SLT services?"
    }


# API MODELS
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    next_suggestion: str


history_store: Dict[str, List[str]] = {}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    q = req.message.strip()
    if not q:
        return ChatResponse(reply="Please enter a question.", next_suggestion="")
    
    search_q = q
    if "data" in q.lower() and "broadband" not in q.lower():
        search_q = f"{q} broadband connection packages"
    
    qvec = embed_query(search_q)
    semantic_results = milvus_search(qvec, SEARCH_TOP_K)
    keyword_results = bm25_search(search_q, k=20)
    # Merge with weighting
    alpha = 0.60  # 40% semantic, 60% keyword
    combined = []

    # Normalize BM25 scores to similar scale
    if keyword_results:
        max_bm = max(k["boosted"] for k in keyword_results) or 1.0
    else:
        max_bm = 1.0

    for r in semantic_results:
        r["combined"] = alpha * r["boosted"]
        combined.append(r)

    for k in keyword_results:
        k["combined"] = (1 - alpha) * (k["boosted"] / max_bm)
        combined.append(k)

    cands = sorted(combined, key=lambda x: x["combined"], reverse=True)

    # optional multi-query expansion
    if ENABLE_MQE:
        exps = await multi_query_expand(q, MQE_QUERIES)
        for e in exps:
            ev = embed_query(e)
            cands += milvus_search(ev, SEARCH_TOP_K//2)
    # dedup
    uniq, final = [], []
    seen = set()
    for c in cands:
        t = c["text"].strip()
        if t and t not in seen:
            seen.add(t)
            final.append(c)
    if not final:
        return ChatResponse(reply=" No relevant information found.", next_suggestion="Try rephrasing your question.")
    reranked = rerank(q, final[:RERANK_TOP_K], RERANK_TOP_K)
    top_chunks = select_diverse_chunks(reranked, CONTEXT_CHUNKS)

    user_history = history_store.get(req.session_id, [])
    ans = generate_answer(q, top_chunks, user_history)

    history_store.setdefault(req.session_id, []).extend([
        f"User: {q}",
        f"AI: {ans['reply']}"
    ])
    
    return ChatResponse(**ans)

# MAIN
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
