import os
import yaml

import hashlib
import json
import time
from pathlib import Path
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")

_config = None
LLM_METRICS_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "logs" / "llm_call_metrics.jsonl"


def _load_config():
    global _config
    if _config is None:
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Configuration file not found at: {CONFIG_PATH}")
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config

def generate(prompt: str, model_key: str, chunk_count: int = None) -> str:
    """
    Generate response for a given prompt and model_key mapping to config.yaml.
    
    Args:
        prompt: The prompt text to send to the LLM.
        model_key: The configuration key mapping to the model name.
        chunk_count: Optional number of retrieved chunks included in the prompt.
        
    Returns:
        The generated text response.
    """
    config = _load_config()
    backend_type = config.get("llm_backend", "ollama")
    model = config.get(model_key, model_key)
    
    # Simple disk-backed prompt cache to avoid repeated heavy LLM calls
    cache_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "logs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "llm_prompt_cache.json"

    key = hashlib.sha256((prompt + "::" + str(model)).encode("utf-8")).hexdigest()
    cache = {}
    try:
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
    except Exception:
        cache = {}

    gen_cfg = config.get("generation", {})

    start_total = time.perf_counter()
    cache_hit = key in cache
    if cache_hit:
        result = cache[key]
        backend_ms = 0.0
    else:
        if backend_type == "ollama":
            from llm.ollama_backend import generate as ollama_generate
            start_backend = time.perf_counter()
            result = ollama_generate(prompt, model)
            backend_ms = (time.perf_counter() - start_backend) * 1000
        elif backend_type == "transformers":
            from llm.transformers_backend import generate as transformers_generate
            start_backend = time.perf_counter()
            result = transformers_generate(prompt, model)
            backend_ms = (time.perf_counter() - start_backend) * 1000
        else:
            raise ValueError(f"Unsupported LLM backend: {backend_type}")

        # Save to cache (best-effort)
        try:
            cache[key] = result
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        except Exception:
            pass

    total_ms = (time.perf_counter() - start_total) * 1000

    # Log LLM call metrics for profiling.
    try:
        LLM_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "model_key": model_key,
            "model": model,
            "cache_hit": cache_hit,
            "prompt_chars": len(prompt),
            "prompt_words": len(prompt.split()),
            "prompt_tokens_approx": int(len(prompt.split()) * 1.33),
            "chunk_count": chunk_count,
            "num_predict": gen_cfg.get("num_predict") if gen_cfg else None,
            "response_chars": len(result),
            "response_words": len(result.split()),
            "response_tokens_approx": int(len(result.split()) * 1.33),
            "backend_ms": backend_ms,
            "total_ms": total_ms,
        }
        with open(LLM_METRICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        pass

    return result
