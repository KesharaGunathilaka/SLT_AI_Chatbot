import aiohttp
import asyncio
from bs4 import BeautifulSoup


# change this to the sitemap URL of the target website
SITEMAP_URL = "https://slt.lk/en/sitemap"
BASE_URL = "https://slt.lk"   # change this to any website
DOMAIN = "slt.lk"

async def fetch_all_urls(timeout_seconds=120):
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        print(f"Fetching sitemap with timeout = {timeout_seconds}s ...")
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

    print(f"\n✅ Found {len(urls)} URLs:\n")
    for url in urls:
        print(url)

    return urls

if __name__ == "__main__":
    asyncio.run(fetch_all_urls(timeout_seconds=120))  # ⏱ change timeout here
