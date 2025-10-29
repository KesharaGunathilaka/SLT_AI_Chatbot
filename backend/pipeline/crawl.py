# stage1_crawl.py
import asyncio
import os
import json
import aiohttp
from bs4 import BeautifulSoup
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
    DefaultMarkdownGenerator,
)

SITEMAP_URL = "https://slt.lk/en/sitemap"
OUTPUT_DIR = "../data"
RAW_DIR = os.path.join(OUTPUT_DIR, "raw")


async def fetch_sitemap_urls():
    """Fetch links from the sitemap page (no JS; simple <a href> scrape)."""
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SLT-Scraper/1.0; +https://example.com/bot)"
    }
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(SITEMAP_URL) as resp:
            resp.raise_for_status()
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "slt.lk" in href:
            urls.append(href)
        elif href.startswith("/"):
            urls.append("https://slt.lk" + href)

    urls = sorted(set(urls))
    print(f"🧭 Found {len(urls)} pages in sitemap")
    return urls


async def crawl_urls(urls, max_pages: int | None = None):
    """Crawl pages with DefaultMarkdownGenerator (no LLM)."""
    os.makedirs(RAW_DIR, exist_ok=True)

    if max_pages:
        urls = urls[:max_pages]

    browser_config = BrowserConfig(verbose=True)
    md_strategy = DefaultMarkdownGenerator()

    # Use markdown_generator (DefaultMarkdownGenerator) directly; do not pass it as extraction_strategy
    # because DefaultMarkdownGenerator is NOT an ExtractionStrategy subclass.
    run_config = CrawlerRunConfig(
        markdown_generator=md_strategy,
        cache_mode=CacheMode.BYPASS,
        excluded_tags=["form", "header", "footer",
                       "nav", "aside", "script", "style"],
        session_id="slt",
    )

    all_results = []
    total = len(urls)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{total}] Crawling: {url}")
            try:
                results = await crawler.arun(url=url, config=run_config)
            except Exception as e:
                print(f"❌ Crawler error for {url}: {e}")
                continue

            if not results:
                print(f"⚠️ No results returned for {url}")
                continue

            for result in results:
                if result.success:
                    all_results.append(
                        {"url": result.url, "content": result.markdown})
                    out_path = os.path.join(RAW_DIR, f"page_{i}.md")
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(result.markdown)
                else:
                    print(f"⚠️ Crawl failed for {url}: {result.error_message}")

    # Save combined JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    combined_path = os.path.join(OUTPUT_DIR, "slt_raw.json")
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"✅ Finished. Saved {len(all_results)} pages")
    print(f"   - Per-page markdown: {RAW_DIR}/page_*.md")
    print(f"   - Combined JSON:     {combined_path}")


async def main(max_pages: int | None = None):
    urls = await fetch_sitemap_urls()
    if not urls:
        print("⚠️ No URLs found. Check the sitemap URL or network.")
        return
    await crawl_urls(urls, max_pages=max_pages)


if __name__ == "__main__":
    # Optional: allow --max argument
    import argparse

    parser = argparse.ArgumentParser(description="Stage 1: Crawl SLT (no LLM)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max pages to crawl")
    args = parser.parse_args()

    asyncio.run(main(max_pages=args.max))
