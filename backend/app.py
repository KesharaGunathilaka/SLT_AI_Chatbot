import os
from time import time as _now
from typing import List, Dict, Any, Optional, Tuple
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from sentence_transformers import SentenceTransformer
try:
    # Optional reranker for better answer accuracy; will gracefully degrade if unavailable
    from sentence_transformers import CrossEncoder  # type: ignore
    _HAS_RERANKER = True
except ImportError:
    CrossEncoder = None  # type: ignore
    _HAS_RERANKER = False
from pymilvus import connections, Collection
from llm_model import query_llm

# CONFIG
URI = os.getenv("ZILLIZ_CLOUD_URI")
TOKEN = os.getenv("ZILLIZ_CLOUD_API_KEY")
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION", "slt_content")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "BAAI/bge-m3")
# NOTE: Ensure this matches the collection schema dim. bge-m3 -> 1024
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
EMBED_QUERY_PREFIX = os.getenv("EMBED_QUERY_PREFIX", "")  # e.g., "query: " for bge family if re-indexed accordingly

# Retrieval tuning
SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "20"))  # retrieve more then rerank
CONTEXT_CHUNKS = int(os.getenv("CONTEXT_CHUNKS", "4"))  # how many chunks to send to LLM
SCORE_THRESHOLD_IP = float(os.getenv("SCORE_THRESHOLD_IP", "0.2"))  # only for IP metric
PRIORITY_BONUS = float(os.getenv("PRIORITY_BONUS", "0.001"))  # small bonus per priority point
RECENCY_BONUS_HALF_LIFE_DAYS = float(os.getenv("RECENCY_BONUS_HALF_LIFE_DAYS", "90"))
ENABLE_RERANK = os.getenv("ENABLE_RERANK", "true").lower() == "true"
RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

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

reranker: Optional[Any] = None
if ENABLE_RERANK and _HAS_RERANKER:
    try:
        reranker = CrossEncoder(RERANK_MODEL)
    except (OSError, RuntimeError, ValueError) as e:
        print(f"Reranker init failed ({RERANK_MODEL}): {e}")
        reranker = None

connections.connect(alias="default", uri=URI, token=TOKEN)
collection = Collection(COLLECTION_NAME)
collection.load()

# Try to detect collection embedding dimension to guard against mismatch
def _detect_collection_dim(coll: Collection, default_dim: int) -> int:
    try:
        for f in coll.schema.fields:
            if getattr(f, "name", None) == "embedding" and getattr(f, "dtype", None) is not None:
                # In Milvus, dim is kept in field params for float vectors
                params = getattr(f, "params", None) or {}
                dim = params.get("dim") or params.get("DIM")
                if dim:
                    return int(dim)
    except (AttributeError, KeyError, TypeError, ValueError) as e:
        print(f"Warn: unable to detect collection dim, using default {default_dim}. Detail: {e}")
    return default_dim

COLLECTION_DIM = _detect_collection_dim(collection, EMBEDDING_DIM)
_DIM_MISMATCH_WARNED = False

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


def _now_ts() -> int:
    return int(_now())


def embed_query(query: str) -> List[float]:
    # Keeping embeddings unnormalized to match how vectors were indexed (metric: IP)
    text = f"{EMBED_QUERY_PREFIX}{query}" if EMBED_QUERY_PREFIX else query
    return embedding_model.encode([text])[0].tolist()


def _days_since(ts: Optional[int]) -> float:
    if not ts:
        return 365.0
    return max(0.0, (_now() - ts) / 86400.0)


def _score_with_boost(raw_score: float, priority: Optional[float], last_updated_at: Optional[int]) -> float:
    # raw_score: Milvus IP similarity (higher is better)
    # Add small boosts for priority and recency
    pr = float(priority or 0.0)
    days = _days_since(last_updated_at)
    # recency bonus decays with half-life
    half_life = max(1.0, RECENCY_BONUS_HALF_LIFE_DAYS)
    recency_bonus = 0.02 * (0.5 ** (days / half_life))
    return raw_score + PRIORITY_BONUS * pr + recency_bonus


def _format_context_with_sources(chunks: List[Dict[str, Any]]) -> Tuple[str, List[str]]:
    lines = []
    sources = []
    for idx, ch in enumerate(chunks, start=1):
        url = ch.get("url") or ""
        txt = ch.get("chunk_text") or ""
        lines.append(f"[Source {idx}] URL: {url}\n{txt}")
        sources.append(url)
    return "\n\n".join(lines), sources


def generate_answer(query: str, context_chunks: List[Dict[str, Any]], history: List[str]) -> Dict[str, str]:
    context_text, sources = _format_context_with_sources(context_chunks)
    history_text = "\n".join([f"- {q}" for q in history[-6:]])

    prompt = f"""
You are an expert assistant for Sri Lanka Telecom.
Answer the user's question using ONLY the information from the provided sources. If the answer is not present in the sources, say you don't know and suggest one clarifying question.

Guidelines:
- Be precise and helpful. Use simple language.
- Prefer the most recent and high-priority information implicitly.
- If listing options (plans, branches), present them clearly and concisely.
- Cite evidence using [Source N] inline where relevant.
- At the end, propose ONE natural follow-up question.

Conversation (last turns):
{history_text}

User question: {query}

Sources:
{context_text}

Format the output exactly as:
Answer: <your answer here with [Source N] citations>
Follow-up question: <one question>
"""

    response = query_llm(prompt)

    # Split into answer + suggestion
    answer, suggestion = response, "Would you like me to provide more details?"
    if isinstance(response, str) and "Follow-up question:" in response:
        parts = response.split("Follow-up question:")
        answer = parts[0].replace("Answer:", "").strip()
        suggestion = parts[1].strip()

    # Append sources list for transparency
    unique_sources = [s for i, s in enumerate(sources) if s and s not in sources[:i]]
    if unique_sources:
        src_block = "\n\nSources:\n" + "\n".join(f"- {u}" for u in unique_sources)
        answer = f"{answer}{src_block}"

    return {
        "reply": answer,
        "next_suggestion": suggestion
    }


def _rerank(query: str, candidates: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    if not candidates:
        return []
    # If reranker available, use it; else rely on boosted Milvus score already applied
    if reranker is not None:
        pairs = [(query, c.get("chunk_text", "")) for c in candidates]
        try:
            scores = reranker.predict(pairs)
            for c, s in zip(candidates, scores):
                c["rerank_score"] = float(s)
            candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        except (RuntimeError, ValueError) as e:
            print(f"Rerank failed: {e}")
    return candidates[:top_n]

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

    # Embed query
    query_vec = embed_query(query)

    # Search in Milvus: get more results, then apply boosting + rerank
    search_params = {"metric_type": "IP", "params": {"nprobe": 16}}
    results = collection.search(
        data=[query_vec],
        anns_field="embedding",
        param=search_params,
        limit=SEARCH_TOP_K,
        output_fields=["chunk_text", "priority", "last_updated_at", "url"],
    )

    if not results or not results[0]:
        return ChatResponse(
            reply="❌ Sorry, I couldn’t find relevant information in the knowledge base. Could you rephrase or be more specific?",
            next_suggestion="Would you like help browsing broadband packages or finding a nearby branch?",
        )

    # Convert hits to dicts and apply preliminary filters/boosts
    hits = []
    for h in results[0]:
        entity = h.entity
        raw_score = float(h.distance) if hasattr(h, "distance") else 0.0
        pr = entity.get("priority")
        ts = entity.get("last_updated_at")
        boosted = _score_with_boost(raw_score, pr, ts)
        # Quick threshold on raw score to filter very weak matches (for IP metric)
        if raw_score < SCORE_THRESHOLD_IP:
            continue
        hits.append({
            "chunk_text": entity.get("chunk_text"),
            "priority": pr,
            "last_updated_at": ts,
            "url": entity.get("url"),
            "raw_score": raw_score,
            "boosted_score": boosted,
        })

    if not hits:
        return ChatResponse(
            reply="I’m not confident I have the right answer from our indexed content. Could you provide a bit more detail?",
            next_suggestion="Would you like to see available SLT broadband plans?",
        )

    # Prefer unique URLs to diversify context
    dedup_by_url: Dict[str, Dict[str, Any]] = {}
    for item in sorted(hits, key=lambda x: x["boosted_score"], reverse=True):
        u = item.get("url") or ""
        if u not in dedup_by_url:
            dedup_by_url[u] = item
    deduped = list(dedup_by_url.values())

    # Rerank best candidates for final context
    best = _rerank(query, deduped[: max(CONTEXT_CHUNKS * 3, 10)], CONTEXT_CHUNKS)

    answer_data = generate_answer(query, best, conversation_history[req.session_id])
    return ChatResponse(**answer_data)

# MAIN
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
