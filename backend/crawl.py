import asyncio
import os
import aiohttp
from bs4 import BeautifulSoup
import re
from crawl4ai import (AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, DefaultMarkdownGenerator)
import hashlib
from urllib.parse import urlparse
from datetime import UTC, datetime
from db import create_pool, create_tables, upsert_page
from classify import classify_page
import uuid

SITEMAP_URL = "https://slt.lk/en/sitemap"   # change this to the sitemap URL of the target website
OUTPUT_DIR = "./data"
RAW_DIR = os.path.join(OUTPUT_DIR, "crawl")
BASE_URL = "https://slt.lk"   # change this to any website
DOMAIN = "slt.lk"             # the domain to check against

LLM_CONCURRENCY = 1

def sanitize_filename(url: str) -> str:
    filename = re.sub(r'https?://', '', url)
    filename = re.sub(r'slt\.lk/', '', filename)
    filename = re.sub(r'en/about-us', 'Ab', filename)
    filename = re.sub(r'en/business', 'Bu', filename)
    filename = re.sub(r'en/broadband', 'Br', filename)
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    if len(filename) > 100:
        filename = filename[:100] + "_truncated"
    return filename + ".md"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def calculate_priority(url: str) -> int:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return 100
    depth = len(path.split("/"))
    return max(100 - depth * 10, 10)


def extract_metadata(html: str, url: str, headers: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title else None
    description = soup.find("meta", attrs={"name": "description"})
    description = description["content"].strip() if description else None
    canonical = soup.find("link", rel="canonical")
    canonical_url = canonical["href"] if canonical else url
    text_only = soup.get_text(" ", strip=True)
    checksum = sha256(text_only)

    metadata = {
        "url": url,
        "scraped_at": datetime.now(UTC),
        "title": title,
        "meta_description": description,
        "canonical_url": canonical_url,
        "checksum": checksum,
        "etag": headers.get("ETag"),
        "last_modified_at": headers.get("Last-Modified"),
        "content_type": headers.get("Content-Type"),
        "http_status": headers.get("Status"),
        "category": None,
        "tags": [],
        "priority": calculate_priority(url),
    }
    return metadata

async def fetch_sitemap_urls():
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(SITEMAP_URL) as resp:
            resp.raise_for_status()
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and DOMAIN in href:
            urls.append(href)
        elif href.startswith("/"):
            urls.append(BASE_URL + href)

    urls = sorted(set(urls))
    print(f"Found {len(urls)} pages in sitemap")
    return urls


async def crawl_urls(urls, pool, max_pages: int | None = None):
    os.makedirs(RAW_DIR, exist_ok=True)

    if max_pages:
        urls = urls[:max_pages]

    browser_config = BrowserConfig(
            verbose=True,
            headless=True
            )
    
    md_strategy = DefaultMarkdownGenerator(
        content_source="cleaned_html",
        options={
            "ignore_images": True,
            "skip_internal_links": True
        }
    )
    
    run_config = CrawlerRunConfig(
        markdown_generator=md_strategy,
        cache_mode=CacheMode.BYPASS,
        excluded_tags=["header", "footer", "aside", "script", "style", "form"],
        session_id="slt",
    )

    llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)
    all_results = []
    total = len(urls)
    processed = 0

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{total}] Crawling: {url}")
            try:
                results = await crawler.arun(url=url, config=run_config)
            except Exception as e:
                print(f"Crawler error for {url}: {e}")
                continue

            if not results:
                print(f"No results returned for {url}")
                continue

            for result in results:
                if result.success:
                    html = getattr(result, "html", None)
                    content_md = result.markdown or ""
                    metadata = extract_metadata(
                        result.html or result.markdown, url, result.response_headers or {}
                    )
                    all_results.append(
                        {"url": result.url, "metadata": metadata, "content": result.markdown})
                    
                    safe_filename = sanitize_filename(url)

                    async with llm_semaphore:
                        classification = await classify_page(metadata, content_md)
                        metadata["category"] = classification.get("category")
                        metadata["tags"] = classification.get("tags") or []
                        llm_raw = classification.get("llm_raw")
                        llm_cleaned = classification.get("llm_cleaned")

                    upsert_result = await upsert_page(pool, safe_filename, url, metadata, content_md, html, llm_raw, llm_cleaned)

                                       
                    out_path = os.path.join(
                        RAW_DIR, f"{safe_filename}")
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(f"---\n")
                        f.write(f"url: {result.url}\n")
                        f.write(f"---\n")
                        for k, v in metadata.items():
                            if v is not None:
                                if k == "tags" and isinstance(v, list):
                                    f.write(f"{k}: {v}\n")
                                else:
                                    f.write(f"{k}: {v}\n")
                        f.write("llm_raw: |\n")
                        for line in (llm_raw or "").splitlines():
                            f.write(f"  {line}\n")
                        f.write("---\n\n")
                        f.write(f"---\n")
                        f.write(f"llm_cleaned_Content: |\n")
                        for line in (llm_cleaned or "").splitlines():
                            f.write(f"  {line}\n")
                        f.write(f"---\n\n")
                        f.write(f"Raw_Content: |\n")
                        f.write(result.markdown)
                    
                    processed += 1
                    print(
                        f"Saved and stored: {url} -> page_id={upsert_result.get('page_id')}")
                    
                else:
                    print(f"Crawl failed for {url}: {result.error_message}")                  

    print(f"✅ Finished. Saved {len(all_results)} pages")
    print(f"   - Per-page markdown: {RAW_DIR}/page_*.md")

async def main(max_pages: int | None = None):
    pool = await create_pool()
    await create_tables(pool)
    urls = await fetch_sitemap_urls()
    if not urls:
        print(" No URLs found. Check the sitemap URL or network.")
        return
    try:
        await crawl_urls(urls, pool, max_pages=max_pages)
    finally:
        await pool.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Crawl SLT Content (with metadata)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max pages to crawl")
    args = parser.parse_args()

    asyncio.run(main(max_pages=args.max))
