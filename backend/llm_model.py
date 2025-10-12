import requests
import os

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Default configuration
DEFAULT_CONFIG = {
    "provider": "ollama",  # options: "ollama", "lmstudio", "groq"
    "ollama_model": "mistral",
    "lmstudio_model": "openai/gpt-oss-20b",
    "groq_model": "openai/gpt-oss-120b",
    #"groq_model": "llama-3.3-70b-versatile",
    #"groq_model": "qwen/qwen3-32b",
    "temperature": 0.3,
    "fallback_to_cloud_llm": True
}


def query_llm(prompt, config=None):
    if config is None:
        config = DEFAULT_CONFIG.copy()

    provider = config.get("provider", "groq")

    if provider == "ollama":
        try:
            return _query_ollama(prompt, config)
        except Exception as e:
            print(f"Ollama failed: {e}")
            if config.get("fallback_to_cloud_llm", True):
                print("Falling back to Groq...")
                return _query_groq(prompt, config)
            else:
                raise

    elif provider == "lmstudio":
        try:
            return _query_lmstudio(prompt, config)
        except Exception as e:
            print(f"LM Studio failed: {e}")
            if config.get("fallback_to_cloud_llm", True):
                print("Falling back to Groq...")
                return _query_groq(prompt, config)
            else:
                raise

    elif provider == "groq":
        return _query_groq(prompt, config)

    else:
        raise ValueError(f"Unknown provider: {provider}")


def _query_ollama(prompt, config):
    payload = {
        "model": config["ollama_model"],
        "prompt": prompt,
        "stream": False
    }
    res = requests.post(OLLAMA_URL, json=payload, timeout=30)
    res.raise_for_status()
    return res.json()["response"].strip()


def _query_lmstudio(prompt, config):
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
    res = requests.post(GROQ_API_URL, headers=headers,
                        json=payload, timeout=30)
    res.raise_for_status()
    data = res.json()
    return data["choices"][0]["message"]["content"].strip()


# if __name__ == "__main__":
#     for provider in ["ollama", "lmstudio", "groq"]:
#         print(f"\n--- Testing {provider.upper()} ---")
#         cfg = DEFAULT_CONFIG.copy()
#         cfg["provider"] = provider
#         response = query_llm("Explain the difference between AI and ML.", cfg)
#         print(response)
