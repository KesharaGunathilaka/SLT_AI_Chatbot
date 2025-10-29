import asyncio
import os
import json
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig, LLMExtractionStrategy
from dotenv import load_dotenv

load_dotenv()


async def main():
    # 1. Browser configuration
    browser_config = BrowserConfig(verbose=True)

    # 2. LLM extraction strategy
    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="groq/openai/gpt-oss-120b", api_token=os.getenv("GROQ_API_KEY")),
        extraction_type="schema",
        instruction="""
        Focus on extracting the *core package information* from the SLT PEO TV "Packages & Charges" page.
        Include: package name, rental, installation charges, features, tariff details, validity, etc.
        Exclude: navigation, ads, buy buttons.
        Output as clean Markdown with sections for each package.
        """,
        input_format="markdown",
        verbose=True,
    )

    # 3) Run config
    run_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS,
        excluded_tags=['form', 'header', 'footer',
                       'nav', 'aside', 'script', 'style'],
        session_id="slt",
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        url = "https://www.slt.lk/en/personal/peo-tv/packages-and-charges"
        result = await crawler.arun(url=url, config=run_config)

        if result.success:
            # Save markdown
            with open("slt_data.md", "w", encoding="utf-8") as f:
                f.write(result.markdown or "")

            # Try parsing extracted JSON (if available)
            extracted_data = None
            if result.extracted_content:
                try:
                    extracted_data = json.loads(result.extracted_content)
                except json.JSONDecodeError:
                    print(
                        "⚠️ Extracted content is not valid JSON. Saving raw text instead.")
                    extracted_data = result.extracted_content

            scraped_data = {
                "url": url,
                "content": extracted_data,
                "markdown": result.markdown,
            }

            output_path = "./slt_peopackages.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)

            print(f"✅ Data saved to: {output_path}")

        else:
            print(f"❌ Crawl failed: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
