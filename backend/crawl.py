import asyncio
import os
import json
import aiohttp
from bs4 import BeautifulSoup
import re
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CrawlerRunConfig,
    CacheMode,
    DefaultMarkdownGenerator,
)
from datetime import datetime

SITEMAP_URL = "https://slt.lk/en/sitemap"
OUTPUT_DIR = "./data"
RAW_DIR = os.path.join(OUTPUT_DIR, "crawl")
BASE_URL = "https://slt.lk"   # change this to any website
DOMAIN = "slt.lk"             # the domain to check against

def sanitize_filename(url: str) -> str:
    filename = re.sub(r'https?://', '', url)
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    if len(filename) > 100:
        filename = filename[:100] + "_truncated"
    return filename + ".md"


async def fetch_sitemap_urls():
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(SITEMAP_URL) as resp:
            resp.raise_for_status()
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")
    urls = []
    # for a in soup.find_all("a", href=True):
    #     href = a["href"]
    #     if href.startswith("http") and "slt.lk" in href:
    #         urls.append(href)
    #     elif href.startswith("/"):
    #         urls.append("https://slt.lk" + href)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and DOMAIN in href:
            urls.append(href)
        elif href.startswith("/"):
            urls.append(BASE_URL + href)

    urls = sorted(set(urls))
    print(f"Found {len(urls)} pages in sitemap")
    return urls


async def crawl_urls(urls, max_pages: int | None = None):
    os.makedirs(RAW_DIR, exist_ok=True)

    if max_pages:
        urls = urls[:max_pages]

    browser_config = BrowserConfig(verbose=True)
    md_strategy = DefaultMarkdownGenerator(
        content_source="fit_html",
        options={"ignore_links": True}
    )
    
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
                print(f"Crawler error for {url}: {e}")
                continue

            if not results:
                print(f"No results returned for {url}")
                continue

            for result in results:
                if result.success:
                    all_results.append(
                        {"url": result.url, "content": result.markdown})
                    safe_filename = sanitize_filename(url)
                    scraped_at = datetime.utcnow().isoformat()
                    out_path = os.path.join(
                        RAW_DIR, f"{safe_filename}")
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(f"---\n")
                        f.write(f"url: {result.url}\n")
                        f.write(f"scraped_at: {scraped_at}\n")
                        f.write(f"---\n\n")
                        f.write(result.markdown)
                else:
                    print(f"Crawl failed for {url}: {result.error_message}")
                    
    # Save combined JSON
    # os.makedirs(OUTPUT_DIR, exist_ok=True)
    # combined_path = os.path.join(OUTPUT_DIR, "slt_raw.json")
    # with open(combined_path, "w", encoding="utf-8") as f:
    #     json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"✅ Finished. Saved {len(all_results)} pages")
    print(f"   - Per-page markdown: {RAW_DIR}/page_*.md")
    # print(f"   - Combined JSON:     {combined_path}")


async def main(max_pages: int | None = None):
    urls = await fetch_sitemap_urls()
    if not urls:
        print(" No URLs found. Check the sitemap URL or network.")
        return
    await crawl_urls(urls, max_pages=max_pages)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 1: Crawl SLT (no LLM)")
    parser.add_argument("--max", type=int, default=None,
                        help="Max pages to crawl")
    args = parser.parse_args()

    asyncio.run(main(max_pages=args.max))
