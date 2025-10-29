import asyncio
import os
import json
import aiohttp
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig, LLMExtractionStrategy, LLMContentFilter, DefaultMarkdownGenerator
from crawl4ai import JsonCssExtractionStrategy
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

SITEMAP_URL = "https://slt.lk/en/sitemap"


async def fetch_sitemap_urls():
    urls = []
    async with aiohttp.ClientSession() as session:
        async with session.get(SITEMAP_URL) as resp:
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "slt.lk" in href:
            urls.append(href)
        elif href.startswith("/"):
            urls.append("https://slt.lk" + href)

    # Remove duplicates
    urls = sorted(set(urls))
    print(f"Found {len(urls)} pages in sitemap")
    return urls


async def crawl_urls(urls):

    # 1. Browser configuration
    browser_config = BrowserConfig(
        verbose=True,
    )

    # 2. LLM extraction strategy
    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider="groq/meta-llama/llama-4-scout-17b-16e-instruct",
                             api_token=os.getenv("GROQ_API_KEY")),
        extraction_type="schema",

        verbose=True,
        chunk_token_threshold=1200,
        overlap_rate=0.1,
        apply_chunking=True,
        extra_args={"temperature": 0.0, "max_tokens": 1000}
    )

    # 3) Crawler run config: skip cache, use extraction
    run_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS,
        excluded_tags=['form', 'header', 'footer',
                       'nav', 'aside', 'script', 'style'],
        session_id="slt",
        # enable_rate_limiting=False,
        # rate_limit_config=None,
        # memory_threshold_percent=70.0,
        # check_interval=1.0,
        # max_session_permit=20,
        # wait_for="js:() => window.loaded === true",
        # display_mode=None,
        # exclude_external_links=True,
    )

    all_results = []

    async with AsyncWebCrawler(config=browser_config) as crawler:

        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] Crawling: {url}")
            results = await crawler.arun(url=url, config=run_config)

            for result in results:
                if result.success:
                    # Print clean content
                    print("Content:", result.markdown)
                    extracted = json.loads(result.extracted_content)

                    all_results.append({
                        "url": result.url,
                        "content": result.markdown,
                        "extracted_data": extracted
                    })

                    with open("../data/slt_full_sitemap.json", "w", encoding="utf-8") as f:
                        json.dump(all_results, f, indent=2, ensure_ascii=False)
                        print(f"✅ Saved {len(all_results)} pages")

                    with open("slt_data.md", "w", encoding="utf-8") as f:
                        f.write(result.markdown)

                    data = json.loads(result.extracted_content)
                    print("Extracted data:", json.dumps(data, indent=2))

                    # Save to a JSON file
                    with open("../data/slt.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    llm_strategy.show_usage()

                else:
                    print(f"Crawl failed: {result.error_message}")


async def main():
    urls = await fetch_sitemap_urls()
    await crawl_urls(urls)

if __name__ == "__main__":
    asyncio.run(main())
