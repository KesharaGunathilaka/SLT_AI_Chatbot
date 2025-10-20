import asyncio
import json
from typing import List
from llm_model import query_llm

DEFAULT_CATEGORIES = [
    # Core Services
    "broadband_services",
    "mobile_services",
    "fixed_telephony",
    "peotv",
    "business_solutions",

    # Customer Operations
    "new_connections",
    "billing_payments",
    "account_management",

    # Support & Contact
    "technical_support",
    "contact_locations",
    "call_centers",
    "branches",

    # Business Units
    "enterprise_cloud",
    "corporate_services",

    # Information
    "promotions_offers",
    "news_announcements",
    "about_company",
    "faq_help"
]


def build_prompt(categories: List[str], url: str, title: str | None, meta_desc: str | None, content_snippet: str):
    categories_text = "\n".join(f"- {c}" for c in categories)
    prompt = f"""
You are a helpful classifier. Given a SINGLE webpage (url and the full text content), return EXACTLY one JSON object and nothing else.

Rules:
1. Choose **one** category. Prefer one of these categories when only appropriate (do not invent new ones). If none fit, set category to "Other: <suggestion>" (example: "Other: Billing").
2. Provide a list of tags (short strings) that describe key topics.
3. Provide a one-line reason for your choice in the `reason` field.
4. Remove irrelevant sections (navigation menus, headers, footers, cookie notices, repeated boilerplate).
5. Produce a cleaned version of the main text content only.

Available categories:
{categories_text}

Now classify this page. Be concise. Output STRICT JSON only.

Input:
url: {url}
full_content: {content_snippet}

Example output:
{{
    "category":"Data Packages",
    "tags":["4G","prepaid","bundle"],
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
        url = metadata.get("url", "").lower()
        title = (metadata.get("title") or "").lower()
        fallback_cat = "General"
        if "broadband" in url or "package" in url or "broadband" in title:
            fallback_cat = "Broadband"
        elif "megaline" in url:
            fallback_cat = "Megaline"
        elif "about" in url:
            fallback_cat = "About"
        parsed = {
            "category": fallback_cat,
            "tags": [],
            "reason": "Fallback rule-based classification",
            "llm_cleaned": content[:20000]
        }
        raw = raw or json.dumps(parsed)

    # normalize parsed fields
    category = parsed.get("category") if parsed.get("category") else "General"
    tags = parsed.get("tags") or []
    llm_cleaned = parsed.pop("llm_cleaned", "")

    return {
        "category": category,
        "tags": tags,
        "reason": parsed.get("reason", ""),
        "llm_cleaned": llm_cleaned,
        "llm_raw": json.dumps(parsed, ensure_ascii=False) if parsed else raw
    }
