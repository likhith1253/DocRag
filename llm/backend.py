import os
import hashlib
import json
import time
from pathlib import Path

from settings import get_settings, resolve_project_path

_config = None
LLM_METRICS_PATH = resolve_project_path(get_settings().log_dir) / "llm_call_metrics.jsonl"


def _load_config():
    global _config
    if _config is None:
        from settings import get_config_dict
        _config = get_config_dict()
    return _config


def generate(prompt: str, model_key: str, chunk_count: int = None, request_id: str = "default", answer_depth: str = None) -> str:
    """
    Generate response for a given prompt and model_key using the configured model key.
    
    Args:
        prompt: The prompt text to send to the LLM.
        model_key: The configuration key mapping to the model name.
        chunk_count: Optional number of retrieved chunks included in the prompt.
        request_id: Unique request ID for stage tracking.
        answer_depth: The detected depth of the question to inform token generation limits.
        
    Returns:
        The generated text response.
    """
    config = _load_config()
    backend_name = str(config.get("llm_backend", "transformers")).lower()
    if backend_name == "ollama":
        model = config.get("ollama_model", get_settings().ollama_model)
    else:
        model = config.get(model_key, config.get("hf_model", model_key))

    gen_cfg = config.get("generation", {}) or {}
    from llm.cache import cache_key, read_cached, write_cached
    decoding = dict(gen_cfg)
    decoding["backend"] = config.get("llm_backend", "transformers")
    decoding["answer_depth"] = answer_depth
    key = cache_key(str(model), prompt, decoding)
    force_generation = os.environ.get("DOCRAG_FORCE_GENERATION", "").lower() in ("1", "true", "yes")

    start_total = time.perf_counter()
    cached_result = None if force_generation else read_cached(key)
    cache_hit = cached_result is not None
    if cache_hit:
        result = cached_result
        backend_ms = 0.0
        print("      ?? [LLM Cache Hit] Returning content-addressed cached output", flush=True)
        try:
            from storage.pipeline_logger import log_stage
            log_stage(request_id, 10, "LLM Content Cache Hit", {"raw_output": result, "cache_hit": True}, latency_ms=0.0)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Could not record cache-hit trace: %s", exc)
    else:
        from llm.backend_factory import get_backend
        import inspect
        backend = get_backend()
        start_backend = time.perf_counter()
        print(f"CALLING {backend.__class__.__name__}.generate()", flush=True)
        parameters = inspect.signature(backend.generate).parameters
        kwargs = {}
        if "request_id" in parameters:
            kwargs["request_id"] = request_id
        if "answer_depth" in parameters:
            kwargs["answer_depth"] = answer_depth
        result = backend.generate(prompt, model, **kwargs)
        backend_ms = (time.perf_counter() - start_backend) * 1000
        if not isinstance(result, str):
            raise TypeError(f"LLM backend returned {type(result).__name__}; expected str")
        write_cached(key, result)

        try:
            from llm.transformers_backend import HFTransformersBackend
            is_hf = isinstance(backend, HFTransformersBackend)
        except ImportError:
            is_hf = False
        if not is_hf:
            try:
                from storage.pipeline_logger import log_stage
                log_stage(request_id, 10, f"{backend.__class__.__name__}.generate", {
                    "raw_output": result, "model": model, "backend": backend.__class__.__name__,
                    "latency_ms": backend_ms
                }, latency_ms=backend_ms)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Could not record generation trace: %s", exc)

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
            "num_predict": gen_cfg.get("num_predict"),
            "cache_key": key,
            "response_chars": len(result),
            "response_words": len(result.split()),
            "response_tokens_approx": int(len(result.split()) * 1.33),
            "backend_ms": backend_ms,
            "total_ms": total_ms,
        }
        with open(LLM_METRICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except OSError as exc:
        import logging
        logging.getLogger(__name__).warning("Could not append LLM metrics: %s", exc)

    return result
