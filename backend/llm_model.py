import requests
import os

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Default configuration
DEFAULT_CONFIG = {
    "use_local": False,
    "local_model": "llama3.1",
    #"groq_model": "openai/gpt-oss-120b",
    "groq_model": "llama-3.3-70b-versatile",
    "temperature": 0.3,
    "fallback_to_cloud_llm": True
}


def query_llm(prompt, config=None):
    if config is None:
        config = DEFAULT_CONFIG.copy()

    if config["use_local"]:
        try:
            payload = {
                "model": config["local_model"],
                "prompt": prompt,
                "stream": False
            }
            res = requests.post(OLLAMA_URL, json=payload,
                                timeout=30)  # Added timeout
            res.raise_for_status()
            return res.json()["response"].strip()
        except Exception as e:
            print(f"Local LLM failed: {e}")
            if config.get("fallback_to_cloud_llm", True):
                print("Falling back to Groq...")
                return _query_groq(prompt, config)
            else:
                raise  # Re-raise the exception if no fallback is enabled

    else:
        return _query_groq(prompt, config)


def _query_groq(prompt, config):
    """Helper function to query Groq API"""
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
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Groq API also failed: {e}")
        raise  # Both providers failed
