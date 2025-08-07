import asyncio
import os
import json
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig, LLMContentFilter, DefaultMarkdownGenerator
from crawl4ai import JsonCssExtractionStrategy
from dotenv import load_dotenv
from crawl4ai import LLMExtractionStrategy
from pydantic import BaseModel
from typing import Optional

load_dotenv()


async def main():

    # 1. Browser configuration
    browser_config = BrowserConfig(
        verbose=True,
    )

    # 2. LLM extraction strategy
    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider="groq/deepseek-r1-distill-llama-70b",
                             api_token=os.getenv("GROQ_API_KEY")),
        extraction_type="schema",

        #     instruction="""
        #     Focus on extracting the *core package information* from the SLT PEO TV "Packages & Charges" page.

        #                 Include:
        #                 - Package name (e.g. PEO Lite, PEO Titanium)
        #                 - Monthly rental
        #                 - Installation or connection charges (if shown)
        #                 - Any channel count or bundled features present (like number of channels)
        #                 - Tariff names and TRC approval details (if in listing)
        #                 - Validity (monthly, annual, etc.)
        #                 - Any other key package details that are consistently formatted
        #                 - information that is clearly structured in the page content

        #                 Exclude:
        #                 - All navigation, header, sidebar, footer, site menus, cookie notices
        #                 - Advertisements or “Buy” buttons

        #                 Output as clean Markdown:
        #                 - Use headings like `## Package: PEO Lite`
        #                 - Present each package as a section
        #                 - Provide key fields in a bullet list
        #                 - Wrap any code or tabular content in Markdown code blocks or tables
        #                         """,

        verbose=True,
        extra_args={"temperature": 0.0, "max_tokens": 2000}
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

    async with AsyncWebCrawler(config=browser_config) as crawler:

        url = "https://slt.lk/en/broadband/packages"

        result = await crawler.arun(
            url=url,
            config=run_config
        )

        if result.success:
            # Print clean content
            print("Content:", result.markdown)

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

if __name__ == "__main__":
    asyncio.run(main())
