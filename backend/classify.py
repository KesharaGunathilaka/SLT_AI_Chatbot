import asyncio
import json
from typing import List
from llm_model import query_llm

DEFAULT_CATEGORIES = [
    "broadband", "promotions", "contact", "news", "new_connections",
    "cloud", "services", "peotv", "megaline", "faq", "about_us"
]


def build_prompt(categories: List[str], url: str, title: str | None, meta_desc: str | None, content_snippet: str):
    categories_text = "\n".join(f"- {c}" for c in categories)
    prompt = f"""
You are a helpful classifier. Given a SINGLE webpage (url, title, meta description, and the full text content), return EXACTLY one JSON object and nothing else.

Rules:
1. Choose **one** category. Prefer one of these categories when only appropriate (do not invent new ones). If none fit, set category to "Other: <suggestion>" (example: "Other: Billing").
2. Provide a list of tags (short strings) that describe key topics.
3. Suggest an integer priority from 0 to 100 (100 = highest). Use higher priority for site root and important pages like pricing, product landing pages, contact, support; lower for deep blog posts.
4. Provide a one-line reason for your choice in the `reason` field.
5. Remove irrelevant sections (navigation menus, headers, footers, cookie notices, repeated boilerplate).
6. Produce a cleaned version of the main text content only.

Available categories:
{categories_text}

Now classify this page. Be concise. Output STRICT JSON only.

Input:
url: {url}
title: {title or ""}
meta_description: {meta_desc or ""}
full_content: {content_snippet}

Example output:
{{
    "category":"Data Packages",
    "tags":["4G","prepaid","bundle"],
    "priority":85,
    "reason":"Pricing/product landing with package details",
    "llm_cleaned":"# Data Packages\\nHere are the available 4G prepaid bundles..."
}}
"""
    return prompt


def safe_parse_json(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except Exception:
                pass
    return None


async def classify_page(metadata: dict, content: str, categories: list | None = None, llm_config: dict | None = None, snippet_max_chars: int = 20000):
    if categories is None:
        categories = DEFAULT_CATEGORIES

    snippet = (content[:snippet_max_chars] +
               "...") if len(content) > snippet_max_chars else content
    prompt = build_prompt(categories, metadata.get("url"), metadata.get(
        "title"), metadata.get("meta_description"), snippet)

    try:
        raw = await asyncio.to_thread(query_llm, prompt, llm_config)
    except Exception as e:
        print("LLM call failed:", e)
        raw = ""

    parsed = safe_parse_json(raw)
    if not parsed:
        # fallback: rule-based small classifier using keywords
        url = metadata.get("url", "").lower()
        title = (metadata.get("title") or "").lower()
        fallback_cat = "General"
        if "data" in url or "package" in url or "data" in title:
            fallback_cat = "Data Packages"
        elif "megaline" in url:
            fallback_cat = "Megaline"
        elif "about" in url:
            fallback_cat = "About"
        parsed = {
            "category": fallback_cat,
            "tags": [],
            "priority": metadata.get("priority", 30),
            "reason": "Fallback rule-based classification",
            "llm_cleaned": content[:20000]
        }
        raw = raw or json.dumps(parsed)

    # normalize parsed fields
    category = parsed.get("category") if parsed.get("category") else "General"
    tags = parsed.get("tags") or []
    try:
        priority = int(parsed.get("priority")) if parsed.get(
            "priority") is not None else metadata.get("priority", 30)
        priority = max(0, min(100, priority))
    except Exception:
        priority = metadata.get("priority", 30)

    llm_cleaned = parsed.pop("llm_cleaned", "")

    return {
        "category": category,
        "tags": tags,
        "priority": priority,
        "reason": parsed.get("reason", ""),
        "llm_cleaned": llm_cleaned,
        "llm_raw": json.dumps(parsed, ensure_ascii=False) if parsed else raw
    }
