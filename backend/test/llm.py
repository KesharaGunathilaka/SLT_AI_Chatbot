import requests
import os
import time

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Default configuration
DEFAULT_CONFIG = {
    "provider": "lmstudio",  # options: "ollama", "lmstudio", "groq"
    "ollama_model": "mistral",
    "lmstudio_model": "openai/gpt-oss-20b",
    "groq_model": "openai/gpt-oss-120b",
    "temperature": 0.3,
    "fallback_to_cloud_llm": True,
    "wait_time": 0,   # seconds to wait before any LLM request
    "max_retries": 5  # max retries for rate limit (429)
}


def query_llm(prompt, config=None):
    base = DEFAULT_CONFIG.copy()
    if config:
        base.update(config)

    wait_time = base.get("wait_time", 0)
    if wait_time > 0:
        print(f"⏳ Waiting {wait_time} seconds before sending request...")
        time.sleep(wait_time)

    provider = base.get("provider", "groq")

    if provider == "ollama":
        try:
            return _query_ollama(prompt, base)
        except Exception as e:
            print(f"Ollama failed: {e}")
            if base.get("fallback_to_cloud_llm", True):
                print("🌐 Falling back to Groq...")
                return _query_groq(prompt, base)
            else:
                raise

    elif provider == "lmstudio":
        try:
            return _query_lmstudio(prompt, base)
        except Exception as e:
            print(f"LM Studio failed: {e}")
            if base.get("fallback_to_cloud_llm", True):
                print("🌐 Falling back to Groq...")
                return _query_groq(prompt, base)
            else:
                raise

    elif provider == "groq":
        return _query_groq(prompt, base)

    else:
        raise ValueError(f"Unknown provider: {provider}")


def _query_ollama(prompt, config):
    time.sleep(config.get("wait_time", 0))
    payload = {
        "model": config["ollama_model"],
        "prompt": prompt,
        "stream": False
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=30)
    res.raise_for_status()
    return res.json()["response"].strip()


def _query_lmstudio(prompt, config):
    time.sleep(config.get("wait_time", 0))
    payload = {
        "model": config["lmstudio_model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config["temperature"]
    }
    res = requests.post(LMSTUDIO_URL, json=payload, timeout=30)
    res.raise_for_status()
    data = res.json()
    return data["choices"][0]["message"]["content"].strip()


def _query_groq(prompt, config):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["groq_model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config["temperature"],
    }

    wait = 5  # start wait time for backoff
    for attempt in range(config.get("max_retries", 5)):
        try:
            res = requests.post(GROQ_API_URL, headers=headers,
                                json=payload, timeout=30)

            # Handle rate limiting gracefully
            if res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", wait))
                print(
                    f"⚠️ Groq rate limit hit. Waiting {retry_after}s before retry ({attempt+1}/{config['max_retries']})...")
                time.sleep(retry_after)
                wait *= 2  # exponential backoff
                continue

            # Other HTTP errors
            res.raise_for_status()

            data = res.json()
            return data["choices"][0]["message"]["content"].strip()

        except requests.exceptions.RequestException as e:
            print(f"❌ Groq request failed (attempt {attempt+1}): {e}")
            time.sleep(wait)
            wait *= 2

    # If all retries fail
    print("❌ Max retries exceeded for Groq API.")
    if config.get("fallback_to_cloud_llm", True):
        print("⚙️ Falling back to LM Studio...")
        return _query_lmstudio(prompt, config)
    raise Exception("Groq API failed after multiple retries.")


# Example usage
# if __name__ == "__main__":
#     prompt = "Explain the difference between AI, ML, and Deep Learning."
#     response = query_llm(prompt, {"provider": "groq", "wait_time": 0})
#     print(response)
