import asyncio
import os
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


async def main():

    md_generator = DefaultMarkdownGenerator(
        content_source="cleaned_html",
        options={
            "ignore_images": True,
            "skip_internal_links": True
        }
    )

    browser_conf = BrowserConfig(headless=True)  # or False to see the browser
    run_conf = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        excluded_tags=["header", "footer", "aside", "script", "style", "form"],
        markdown_generator=md_generator
    )

    async with AsyncWebCrawler(config=browser_conf) as crawler:
        result = await crawler.arun(
            url="https://slt.lk/en/node/5016",
            #  url="https://slt.lk/index.php/en/broadband/packages",
            #   url="https://slt.lk/en/personal/peo-tv/packages-and-charges",
            config=run_conf
        )
        print(result.markdown)

        markdown = result.markdown or ""
        os.makedirs("output", exist_ok=True)
        output_path = "output/branch.md"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"✅ Clean Markdown saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
