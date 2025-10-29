import os
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from PIL import Image
from io import BytesIO
import pytesseract
from llm_ollama import query_ollama
from tqdm import tqdm

BASE_URL = "https://slt.lk/index.php/en/broadband/packages"
VISITED, DATA = set(), {}
FAILED_IMAGES = set()
MAX_DEPTH, TIMEOUT = 5, 300  # seconds
start_time = time.time()


def normalize(url):
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment="")).rstrip("/")


def extract_ocr(img_url):
    try:
        if any(img_url.lower().endswith(x) for x in [".svg", ".webp", ".gif"]):
            return None
        res = requests.get(img_url, timeout=5)
        if len(res.content) < 1024 * 50:
            return None  # Skip tiny images
        img = Image.open(BytesIO(res.content)).convert("RGB")
        text = pytesseract.image_to_string(img).strip()
        return {"src": img_url, "text": text}
    except:
        FAILED_IMAGES.add(img_url)
        return None


def crawl(url, depth=0):
    if time.time() - start_time > TIMEOUT or depth > MAX_DEPTH:
        return
    url = normalize(url)
    if url in VISITED or not url.startswith(BASE_URL):
        return
    print(f"Scraping: {url}")
    VISITED.add(url)

    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        text = " ".join(p.get_text(strip=True)
                        for p in soup.find_all(["h1", "h2", "p", "li"]))
        ocrs = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if src:
                ocr = extract_ocr(urljoin(url, src))
                if ocr:
                    ocrs.append(ocr)
        full = f"Page URL: {url}\n\n{text}\n\nOCR Content:\n" + \
            "\n".join(img['text'] for img in ocrs if img['text'])

        # full = text + "\n" + "\n".join(img['text']
        #                                for img in ocrs if img['text'])
        # summary = query_ollama(
        #     f"Summarize this page in bullet points:\n\n{full}")
        DATA[url] = {
            "title": soup.title.string if soup.title else url,
            "text": full,
            "ocr_images": ocrs
        }
        for a in soup.find_all("a", href=True):
            crawl(urljoin(url, a["href"]), depth+1)
    except Exception as e:
        print(f"Error scraping {url}: {e}")


if __name__ == "__main__":
    crawl(BASE_URL)
    os.makedirs("data", exist_ok=True)
    with open("data/index.json", "w", encoding="utf8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)
    print(f"✅ Finished. {len(DATA)} pages saved.")
