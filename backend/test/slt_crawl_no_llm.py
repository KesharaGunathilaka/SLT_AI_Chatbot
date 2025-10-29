import asyncio
import os
import re
import json
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


def strip_header_footer_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    selectors = ["header", "footer", "#header", "#footer",
                 ".header", ".footer", ".site-footer", "aside"]
    for sel in selectors:
        for el in soup.select(sel):
            el.decompose()
    return str(soup)


def html_to_plain_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


def extract_packages_from_text(text: str):
    """Extract package details from SLT package text using simple regex patterns."""
    packages = []
    blocks = re.split(r"(?=Trio|HBB|Any\s?Beat)", text)  # crude splitter
    for block in blocks:
        name_match = re.match(r"([A-Za-z\s]+)", block)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        # Extract known fields
        rental = re.search(r"Monthly Rental\s*Rs\.?(\d+)", block)
        startup = re.search(r"Startup Fee[:\s]*Rs\.?(\d+)", block)
        features = re.findall(
            r"(\d+\s*GB.*?|Unlimited.*?Calls|PEOTV.*?Channels|Eazy Storage)", block)
        packages.append({
            "package_name": name,
            "monthly_rental": f"Rs.{rental.group(1)}" if rental else None,
            "startup_fee": f"Rs.{startup.group(1)}" if startup else None,
            "features": features or [],
            "raw_text": block.strip()
        })
    return packages


async def main():
    url = "https://slt.lk/index.php/en/broadband/packages"
    browser_cfg = BrowserConfig(headless=True, verbose=True)
    md_gen = DefaultMarkdownGenerator(
        content_source="fit_html", options={"ignore_links": True})

    run_cfg = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,
        markdown_generator=md_gen,
        excluded_tags=["form", "header", "footer",
                       "nav", "aside", "script", "style"]
    )

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)
        raw_html = getattr(result, "raw_html", None) or getattr(
            result, "html", None)

        if not raw_html:
            print("No raw HTML found.")
            return

        cleaned_html = strip_header_footer_from_html(raw_html)
        cleaned_text = html_to_plain_text(cleaned_html)

        os.makedirs("output", exist_ok=True)
        json_path = "output/slt_packages.json"
        txt_path = "output/slt_packages.txt"

        # Save plain text for debugging
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(cleaned_text)

        # Extract structured info
        packages = extract_packages_from_text(cleaned_text)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(packages, f, indent=2, ensure_ascii=False)

        print(f"✅ Extracted {len(packages)} packages → {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
