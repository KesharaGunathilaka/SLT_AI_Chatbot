import os
import math
from typing import List, Dict, Tuple, Optional, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from sentence_transformers import SentenceTransformer
try:
    from FlagEmbedding import FlagReranker  # type: ignore
    _FLAG_RERANK_AVAILABLE = True
except Exception:
    _FLAG_RERANK_AVAILABLE = False

try:
    from sentence_transformers import CrossEncoder  # type: ignore
    _CROSS_ENCODER_AVAILABLE = True
except Exception:
    _CROSS_ENCODER_AVAILABLE = False
from pymilvus import connections, Collection
from llm_model import query_llm

# CONFIG
URI = os.getenv("ZILLIZ_CLOUD_URI")
TOKEN = os.getenv("ZILLIZ_CLOUD_API_KEY")
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION", "slt_content")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# Retrieval/search tuning
SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "20"))
CONTEXT_CHUNKS = int(os.getenv("CONTEXT_CHUNKS", "4"))
SCORE_THRESHOLD_IP = float(os.getenv("SCORE_THRESHOLD_IP", "0.2"))
PRIORITY_BONUS = float(os.getenv("PRIORITY_BONUS", "0.001"))  # weight per priority point [0-100]
RECENCY_BONUS_HALF_LIFE_DAYS = float(os.getenv("RECENCY_BONUS_HALF_LIFE_DAYS", "90"))

# Reranking config
ENABLE_RERANK = os.getenv("ENABLE_RERANK", "true").lower() == "true"
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", str(max(CONTEXT_CHUNKS * 3, 12))))

# Multi-query expansion (optional)
ENABLE_MQE = os.getenv("ENABLE_MQE", "false").lower() == "true"
MQE_QUERIES = int(os.getenv("MQE_QUERIES", "2"))

# FASTAPI SETUP
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MODEL + VECTOR DB
embedding_model = SentenceTransformer(EMBEDDING_MODEL)

# Reranker initialization (lazy loaded on first use)
_reranker_model: Optional[Any] = None
_cross_encoder_model: Optional[Any] = None

connections.connect(alias="default", uri=URI, token=TOKEN)
collection = Collection(COLLECTION_NAME)
collection.load()

# REQUEST/RESPONSE SCHEMA


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"  # for multi-user support


class ChatResponse(BaseModel):
    reply: str
    next_suggestion: str


# CONVERSATION MEMORY
conversation_history: Dict[str, List[str]] = {}

# HELPERS


def embed_query(query: str) -> List[float]:
    return embedding_model.encode([query])[0].tolist()


def _ensure_reranker() -> Tuple[Optional[Any], str]:
    """Lazy init and return reranker model with provider label."""
    global _reranker_model, _cross_encoder_model
    if not ENABLE_RERANK:
        return None, "disabled"
    if _reranker_model is None and _FLAG_RERANK_AVAILABLE:
        try:
            # use fp16 for speed if available; will fallback on CPU
            _reranker_model = FlagReranker(RERANK_MODEL, use_fp16=True)
            return _reranker_model, "flagembedding"
        except Exception:
            _reranker_model = None
    if _cross_encoder_model is None and _CROSS_ENCODER_AVAILABLE:
        try:
            _cross_encoder_model = CrossEncoder(RERANK_MODEL)
            return _cross_encoder_model, "cross-encoder"
        except Exception:
            _cross_encoder_model = None
    return None, "unavailable"


def _apply_metadata_boost(base_score: float, priority: Optional[float], last_updated_ts: Optional[int]) -> float:
    """
    Apply priority and recency boosts to the base vector similarity score (IP).

    - priority: expected 0..100, scaled by PRIORITY_BONUS
    - recency: exponential decay with half-life RECENCY_BONUS_HALF_LIFE_DAYS
    Returns adjusted score.
    """
    score = base_score
    # Priority boost
    if priority is not None:
        try:
            p = float(priority)
            score += PRIORITY_BONUS * max(0.0, min(100.0, p))
        except Exception:
            pass

    # Recency boost
    if last_updated_ts:
        try:
            from time import time as _time_now
            now_ts = int(_time_now())
            age_days = max(0.0, (now_ts - int(last_updated_ts)) / 86400.0)
            # recency factor: exp(-ln(2) * age / half_life)
            if RECENCY_BONUS_HALF_LIFE_DAYS > 0:
                recency_factor = math.exp(-math.log(2) * age_days / RECENCY_BONUS_HALF_LIFE_DAYS)
                score += 0.05 * recency_factor  # small bounded recency bonus
        except Exception:
            pass
    return score


def _search_milvus(query_vec: List[float], limit: int) -> List[Dict[str, Any]]:
    search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
    results = collection.search(
        data=[query_vec],
        anns_field="embedding",
        param=search_params,
        limit=limit,
        output_fields=["chunk_text", "priority", "last_updated_at", "url", "category", "chunk_index"],
    )
    hits: List[Dict[str, Any]] = []
    if results and results[0]:
        for hit in results[0]:
            # hit.distance is IP score (higher is better)
            entity = hit.entity
            base_score = float(hit.distance)

            # Access fields as attributes or via dict-style indexing
            chunk_text = getattr(entity, "chunk_text", "")
            priority = getattr(entity, "priority", None)
            last_updated_at = getattr(entity, "last_updated_at", None)
            url = getattr(entity, "url", None)
            category = getattr(entity, "category", None)
            chunk_index = getattr(entity, "chunk_index", None)

            boosted = _apply_metadata_boost(base_score, priority, last_updated_at)

            hits.append({
                "text": chunk_text,
                "score": base_score,
                "boosted_score": boosted,
                "url": url,
                "category": category,
                "chunk_index": chunk_index,
            })
    # Filter by threshold on base IP score first to keep quality
    hits = [h for h in hits if h["score"] >= SCORE_THRESHOLD_IP]
    # Then sort by boosted score
    hits.sort(key=lambda x: x["boosted_score"], reverse=True)
    return hits


def _multi_query_expand(user_query: str, n: int) -> List[str]:
    """Use the LLM to generate n paraphrases or related sub-queries for recall boost."""
    if n <= 0:
        return []
    prompt = f"""
Paraphrase or expand the following question into {n} diverse, short queries that might retrieve complementary relevant documents. Return each on a new line, no numbering, no quotes.

Question: {user_query}
"""
    try:
        raw = query_llm(prompt)
        lines = [l.strip("- •\t ") for l in raw.splitlines() if l.strip()]
        # Keep top-N unique
        seen = set()
        out: List[str] = []
        for l in lines:
            if l not in seen:
                out.append(l)
                seen.add(l)
            if len(out) >= n:
                break
        return out
    except Exception:
        return []


def _rerank(query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    if not candidates:
        return []
    model, provider = _ensure_reranker()
    if not model:
        # Fallback: return by boosted score if no reranker
        return sorted(candidates, key=lambda x: x["boosted_score"], reverse=True)[:top_k]

    pairs = [(query, c["text"]) for c in candidates]
    try:
        if provider == "flagembedding":
            # returns relevance score per pair
            scores = model.compute_score(pairs, normalize=True)
        else:
            # CrossEncoder returns scores for all pairs
            scores = model.predict(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        return sorted(candidates, key=lambda x: x.get("rerank_score", x["boosted_score"]), reverse=True)[:top_k]
    except Exception:
        # On failure, degrade gracefully
        return sorted(candidates, key=lambda x: x["boosted_score"], reverse=True)[:top_k]


def generate_answer(query: str, context_chunks: List[str], history: List[str]) -> Dict[str, str]:
    context_text = "\n\n".join(context_chunks)
    history_text = "\n".join(
        [f"- {q}" for q in history[-5:]])  # last 5 questions

    prompt = f"""
You are an assistant for Sri Lanka Telecom.
Use the context below to answer the user's question.

Context:
{context_text}

Conversation History:
{history_text}

Current User Question: {query}

1. Provide a clear helpful answer.
2. Then, suggest ONE next natural follow-up question related to the user’s interest.
Format output like this:

Answer: <your answer here>
Follow-up question: <next suggested question>
"""

    response = query_llm(prompt)

    # Split into answer + suggestion
    answer, suggestion = response, "Would you like me to provide more details?"

    if "Follow-up question:" in response:
        parts = response.split("Follow-up question:")
        answer = parts[0].replace("Answer:", "").strip()
        suggestion = parts[1].strip()

    return {
        "reply": answer,
        "next_suggestion": suggestion
    }

# ROUTES


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    query = req.message.strip()
    if not query:
        return ChatResponse(reply="⚠️ Please enter a valid question.", next_suggestion="")

    # Update history
    if req.session_id not in conversation_history:
        conversation_history[req.session_id] = []
    conversation_history[req.session_id].append(query)

    # Embed + retrieve (with optional multi-query expansion)
    all_candidates: List[Dict[str, Any]] = []

    # main query
    main_vec = embed_query(query)
    all_candidates.extend(_search_milvus(main_vec, SEARCH_TOP_K))

    # expanded queries for recall
    if ENABLE_MQE and MQE_QUERIES > 0:
        expansions = _multi_query_expand(query, MQE_QUERIES)
        for q in expansions:
            vec = embed_query(q)
            all_candidates.extend(_search_milvus(vec, max(SEARCH_TOP_K // 2, CONTEXT_CHUNKS * 3)))

    # Deduplicate by text to avoid repeats
    deduped: List[Dict[str, Any]] = []
    seen_text = set()
    for c in all_candidates:
        t = c["text"].strip()
        if not t or t in seen_text:
            continue
        seen_text.add(t)
        deduped.append(c)

    if not deduped:
        return ChatResponse(
            reply="❌ Sorry, I couldn’t find any relevant information.",
            next_suggestion="Would you like me to help with SLT broadband packages?",
        )

    # Rerank and pick final context
    reranked = _rerank(query, deduped[:RERANK_TOP_K], top_k=max(CONTEXT_CHUNKS, 4))
    top_chunks = [c["text"] for c in reranked[:CONTEXT_CHUNKS]]

    answer_data = generate_answer(query, top_chunks, conversation_history[req.session_id])

    return ChatResponse(**answer_data)

# MAIN
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
