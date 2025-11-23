import requests
import os
import time

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_KEY_BACKUP = os.getenv("GROQ_API_KEY_BACKUP")

# Default configuration
DEFAULT_CONFIG = {
    "provider": "ollama",  # options: "ollama", "lmstudio", "groq"
    "ollama_model": "mistral",
    "lmstudio_model": "openai/gpt-oss-20b",
    "groq_model": "openai/gpt-oss-120b",
    "backup_model": "openai/gpt-oss-120b",
    #"backup_model": "llama-3.3-70b-versatile",
    #"groq_model": "llama-3.3-70b-versatile",
    #"groq_model": "qwen/qwen3-32b",
    "temperature": 0.1,
    "wait_time": 2,   # seconds to wait before any LLM request
    "max_retries": 3,  # max retries for rate limit (429)
    "fallback_to_cloud_llm": False
}


def query_llm(prompt, config=None):
    base = DEFAULT_CONFIG.copy()
    if config:
        base.update(config)

    wait_time = base.get("wait_time", 0)
    if wait_time > 0:
        print(f" Waiting {wait_time} seconds before sending request...")
        time.sleep(wait_time)

    provider = base.get("provider", "groq")

    if provider == "ollama":
        try:
            return _query_ollama(prompt, base)
        except Exception as e:
            print(f"Ollama failed: {e}")
            if base.get("fallback_to_cloud_llm", True):
                print("Falling back to Groq...")
                return _query_groq(prompt, base)
            else:
                raise

    elif provider == "lmstudio":
        try:
            return _query_lmstudio(prompt, base)
        except Exception as e:
            print(f"LM Studio failed: {e}")
            if base.get("fallback_to_cloud_llm", True):
                print("Falling back to Groq...")
                return _query_groq(prompt, base)
            else:
                raise

    elif provider == "groq":
        return _query_groq(prompt, base)
    
    elif provider == "backup":
        return _query_backup(prompt, base)

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

    try:
        res = requests.post(GROQ_API_URL, headers=headers,
                            json=payload, timeout=30)

        if res.status_code == 429:
            print("Groq rate limit hit. Falling back to backup model...")
            if config.get("fallback_to_cloud_llm", True):
                return _query_backup(prompt, config)
            else:
                raise Exception("Groq rate limit exceeded")

        res.raise_for_status()

        data = res.json()
        return data["choices"][0]["message"]["content"].strip()

    except requests.exceptions.RequestException as e:
        print(f"Groq request failed: {e}")
        if config.get("fallback_to_cloud_llm", True):
            print("Falling back to Backup model...")
            return _query_backup(prompt, config)
        raise Exception(f"Groq API failed: {e}")


def _query_backup(prompt, config):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY_BACKUP}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["backup_model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config["temperature"],
    }

    wait = 5
    max_retries = config.get("max_retries", 5)
    for attempt in range(max_retries):
        try:
            res = requests.post(GROQ_API_URL, headers=headers,
                                json=payload, timeout=30)

            if res.status_code == 429:
                retry_after = int(res.headers.get("Retry-After", wait))
                print(
                    f"Backup model rate limited. Waiting {retry_after}s before retry ({attempt+1}/{max_retries})...")
                time.sleep(retry_after)
                wait *= 2
                continue

            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()

        except requests.exceptions.RequestException as e:
            print(
                f"Backup request failed (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(wait)
            wait *= 2

    raise Exception("Backup model request failed after multiple retries.")
