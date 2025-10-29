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
        You are a data extraction assistant.  
        Your goal is to extract *clean, structured, and detailed* package information from the SLT PEO TV “Packages & Charges / Packages & Tariff” page.

        **Extraction Focus**  
        - For each PEO TV package plan, capture:
        1. **Package name / title**  
        2. **Rental / monthly fee**  
        3. **Installation / activation charges (if any)**  
        4. **Included features / channels / content** (e.g. category of channels, special packages)  
        5. **Tariff or rate breakdowns** (if tiers, extra add-ons, incremental fees)  
        6. **Validity / duration** (if the package is time-bound or trial)  
        7. **Any conditions / notes / disclaimers** (e.g. “for new customers”, “limited time offer”)  

        - **Exclude** irrelevant content: site navigation, menus, ads, “buy now” buttons, header/footer boilerplate, CSS/JS, unrelated text.

        **Output Format**  
        - Output as **Markdown**, organized neatly with sections or subsections.  
        - Use consistent field names (e.g. “Package Name”, “Monthly Fee”, “Installation Charge”, “Features”, “Tariff Details”, “Validity / Notes”).  
        - If certain fields are not applicable, you may omit or mark as `N/A`.  
        - Do not output raw HTML or markup. Only clean text, and structured markdown.

        **Additional Guidelines**  
        - If a package has multiple tiers or optional add-ons, present them as sub-items or nested bullet lists.  
        - Ensure numbers (like fees) are output as text but preserve currency symbols if present (e.g. “Rs. 1200”, “LKR 1,800”).  
        - If possible, detect units (e.g. “per month”, “per year”) and include them.  
        - If the page uses tables or grids, interpret them and flatten into consistent fields.  
        - If there are multiple languages or bilingual text, prefer the English version (if available), but you may capture both if that’s useful.

        **Example Output Template**

        ```markdown
        ### Package Name: XYZ Plan

        - **Monthly Fee**: Rs. 1,200  
        - **Installation / Activation Charge**: Rs. 500  
        - **Features / Included Channels**:  
        - Channel A, Channel B, Channel C  
        - Sports pack, Movie pack (if included)  
        - **Tariff / Breakdown**:  
        - Base: Rs. 1,200  
        - Add-on (Sports): + Rs. 300  
        - Pay-per-view: as per standard rates  
        - **Validity / Notes**:  
        - Valid for 30 days  
        - Offer only for new customers, etc. 
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

            output_path = "./slt_peo_packages.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(scraped_data, f, ensure_ascii=False, indent=4)

            print(f"✅ Data saved to: {output_path}")

        else:
            print(f"❌ Crawl failed: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
